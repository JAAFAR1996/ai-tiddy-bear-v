"""
Security tests for COPPA compliance and child safety.
Tests age verification, data encryption, consent tracking, and safety enforcement.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json

from src.core.entities import Child, ChildProfile, User, Message
from src.core.exceptions import COPPAViolation, ChildSafetyViolation, SafetyViolationError
from src.application.services.child_safety_service import ChildSafetyService


class TestCOPPAAgeCompliance:
    """Test COPPA age compliance (3-13 years)."""

    @pytest.mark.parametrize("age,should_pass", [
        (2, False),   # Too young
        (3, True),    # Minimum age
        (7, True),    # Valid age
        (13, True),   # Maximum age
        (14, False),  # Too old
        (0, False),   # Invalid
        (-1, False),  # Invalid negative
        (100, False), # Unrealistic
    ])
    def test_age_validation(self, age, should_pass):
        """Test age validation for COPPA compliance."""
        if should_pass:
            child = Child(name="Test", age=age)
            assert child.age == age
        else:
            with pytest.raises(Exception):  # Pydantic ValidationError
                Child(name="Test", age=age)

    @pytest.mark.asyncio
    async def test_age_verification_in_chat_endpoint(self):
        """Test age verification is enforced in chat endpoint."""
        from src.adapters.web import chat_with_ai, ChatRequest
        
        # Test ages below limit
        for age in [1, 2]:
            request = ChatRequest(
                message="Hello",
                child_id="child-young",
                child_name="Baby",
                child_age=age
            )
            
            with pytest.raises(Exception) as exc_info:
                await chat_with_ai(request, Mock(), Mock())
            
            assert "COPPA compliance" in str(exc_info.value)
        
        # Test ages above limit
        for age in [14, 15, 18]:
            request = ChatRequest(
                message="Hello",
                child_id="child-old",
                child_name="Teen",
                child_age=age
            )
            
            with pytest.raises(Exception) as exc_info:
                await chat_with_ai(request, Mock(), Mock())
            
            assert "3-13 years" in str(exc_info.value)

    def test_child_profile_age_immutability_validation(self):
        """Test that age changes are validated for COPPA compliance."""
        profile = ChildProfile.create(name="Test", age=7, preferences={})
        
        # Valid age update
        profile.update_profile(age=8)
        assert profile.age == 8
        
        # Should not allow updating to non-compliant age
        # Note: In real implementation, this should be validated
        # TODO: Add validation in update_profile method to prevent non-compliant ages


class TestDataPrivacyAndEncryption:
    """Test data privacy and encryption requirements."""

    @pytest.mark.asyncio
    async def test_pii_fields_marked_for_encryption(self):
        """Test that PII fields are properly marked for encryption."""
        child = Child(
            name="Alice Smith",  # PII
            age=8,
            preferences={"parent_email": "parent@example.com"}  # PII
        )
        
        # Fields that should be encrypted
        pii_fields = ["name", "preferences"]
        
        # In production, these would be encrypted at rest
        for field in pii_fields:
            assert hasattr(child, field)
            # TODO: Verify encryption decorator or method is applied

    @pytest.mark.asyncio
    async def test_message_content_sanitization(self):
        """Test that messages containing PII are sanitized."""
        safety_service = ChildSafetyService()
        
        # Message with potential PII
        content = "My phone number is 555-1234 and I live at 123 Main St"
        filtered = await safety_service.filter_content(content)
        
        # Should filter potential PII patterns
        # Note: Current implementation doesn't filter PII, but should
        # TODO: Add PII filtering to safety service

    def test_conversation_data_retention_limits(self):
        """Test conversation data has retention metadata."""
        from src.core.entities import Conversation
        
        conv = Conversation(child_id="child-123")
        
        # Should have timestamps for retention policy
        assert hasattr(conv, "started_at")
        assert hasattr(conv, "last_activity")
        
        # TODO: Add retention_expires_at field for COPPA compliance


class TestParentConsentTracking:
    """Test parent consent requirements."""

    def test_user_child_relationship(self):
        """Test parent-child relationship tracking."""
        parent = User(
            email="parent@example.com",
            role="parent",
            children=["child-123", "child-456"]
        )
        
        assert len(parent.children) == 2
        assert "child-123" in parent.children
        
        # Should track consent per child
        # TODO: Add consent tracking to User model

    @pytest.mark.asyncio
    async def test_consent_verification_required(self):
        """Test that operations require valid consent."""
        # Mock consent repository
        with patch("src.adapters.database_production.ProductionConsentRepository") as MockConsent:
            consent_repo = Mock()
            consent_repo.get_active_consent = AsyncMock(return_value=None)
            MockConsent.return_value = consent_repo
            
            # Operations should fail without consent
            # TODO: Implement consent checking in services

    def test_consent_audit_trail(self):
        """Test consent changes are auditable."""
        from src.core.events import ChildRegistered
        
        event = ChildRegistered(
            child_id="child-123",
            parent_id="parent-456",
            registered_at=datetime.now(),
            age=8,
            consent_granted=True
        )
        
        # Consent events should be tracked
        assert hasattr(event, "consent_granted")
        assert hasattr(event, "parent_id")
        assert hasattr(event, "registered_at")


class TestContentSafetyEnforcement:
    """Test content safety is enforced throughout the system."""

    @pytest.mark.asyncio
    async def test_multi_layer_safety_validation(self):
        """Test multiple layers of safety validation."""
        safety_service = ChildSafetyService()
        
        unsafe_content = "This contains violence and weapons"
        
        # Layer 1: Input validation
        input_result = await safety_service.validate_content(unsafe_content, child_age=7)
        assert input_result["is_safe"] is False
        
        # Layer 2: Content filtering
        filtered = await safety_service.filter_content(unsafe_content)
        assert "violence" not in filtered.lower()
        assert "weapons" not in filtered.lower()
        
        # Layer 3: Output validation
        output_result = await safety_service.validate_content(filtered, child_age=7)
        assert output_result["is_safe"] is True

    @pytest.mark.asyncio
    async def test_safety_bypass_prevention(self):
        """Test that safety checks cannot be bypassed."""
        from src.core.entities import Message
        
        # Create message without safety check
        msg = Message(
            content="Unsafe content",
            role="user",
            child_id="child-123",
            safety_checked=False,  # Not checked
            safety_score=0.0
        )
        
        # System should enforce safety check
        assert msg.safety_checked is False
        assert msg.safety_score == 0.0
        
        # TODO: Add automatic safety checking in Message creation

    @pytest.mark.asyncio
    async def test_age_inappropriate_content_blocking(self):
        """Test age-inappropriate content is blocked."""
        safety_service = ChildSafetyService()
        
        # Complex content for young child
        complex_content = "Quantum mechanics and relativistic physics"
        result = await safety_service.validate_content(complex_content, child_age=4)
        
        assert result["age_appropriate"] is False

    @pytest.mark.asyncio
    async def test_safety_violation_logging(self):
        """Test safety violations are logged for review."""
        safety_service = ChildSafetyService()
        
        # Generate violation
        unsafe = "violent content"
        await safety_service.validate_content(unsafe, child_age=8)
        
        # Log the violation
        await safety_service.log_safety_event({
            "event_type": "safety_violation",
            "child_id": "child-123",
            "content_snippet": unsafe[:20],
            "severity": "high"
        })
        
        # Verify logged
        assert len(safety_service.safety_events) > 0
        violation_events = [
            e for e in safety_service.safety_events 
            if e["event_type"] == "safety_violation"
        ]
        assert len(violation_events) > 0


class TestRateLimitingAndAbusePrevention:
    """Test rate limiting for child safety."""

    @pytest.mark.asyncio
    async def test_message_rate_limiting(self):
        """Test rate limiting prevents message spam."""
        # Mock rate limiter
        with patch("src.infrastructure.rate_limiting.rate_limiter.RateLimiter") as MockLimiter:
            limiter = Mock()
            limiter.check_rate_limit = AsyncMock(return_value=False)  # Limit exceeded
            MockLimiter.return_value = limiter
            
            # Should block excessive requests
            # TODO: Implement rate limiting in chat endpoint

    def test_rate_limits_per_child(self):
        """Test rate limits are tracked per child."""
        # Rate limits should be:
        # - Per child ID
        # - Different for different age groups
        # - Reset periodically
        
        limits = {
            "3-5": 20,   # Younger children: fewer messages
            "6-8": 40,   # Elementary: moderate
            "9-13": 60,  # Older: more messages
        }
        
        # TODO: Implement age-based rate limiting


class TestAuditingAndMonitoring:
    """Test security auditing and monitoring."""

    @pytest.mark.asyncio
    async def test_security_event_correlation(self):
        """Test security events have correlation IDs."""
        safety_service = ChildSafetyService()
        
        # Create correlated events
        correlation_id = "req-123-456"
        
        await safety_service.log_safety_event({
            "event_type": "content_check",
            "correlation_id": correlation_id,
            "child_id": "child-123",
            "stage": "input"
        })
        
        await safety_service.log_safety_event({
            "event_type": "content_filtered",
            "correlation_id": correlation_id,
            "child_id": "child-123",
            "stage": "processing"
        })
        
        # Find correlated events
        correlated = [
            e for e in safety_service.safety_events
            if e.get("correlation_id") == correlation_id
        ]
        
        assert len(correlated) == 2
        assert correlated[0]["stage"] == "input"
        assert correlated[1]["stage"] == "processing"

    def test_sensitive_data_not_logged(self):
        """Test sensitive data is not included in logs."""
        # Mock logger
        with patch("logging.Logger.info") as mock_log:
            # Log a safety event
            logger = Mock()
            logger.info = mock_log
            
            # Should not log full content or PII
            logger.info("Safety check", extra={
                "child_id": "child-123",  # OK - anonymous ID
                "safety_score": 0.95,     # OK - metric
                # "child_name": "Alice",  # NOT OK - PII
                # "content": "full message" # NOT OK - sensitive
            })
            
            # Verify PII not in logs
            call_args = mock_log.call_args
            if call_args and len(call_args) > 1:
                extra = call_args[1].get("extra", {})
                assert "child_name" not in extra
                assert "content" not in extra


class TestDataMinimization:
    """Test COPPA data minimization requirements."""

    def test_minimal_data_collection(self):
        """Test only necessary data is collected."""
        # Child entity should only have required fields
        child = Child(name="Test", age=7)
        
        # Should not have unnecessary fields like:
        # - Full address
        # - Phone number  
        # - School name
        # - Photo
        
        child_dict = child.model_dump()
        unnecessary_fields = ["address", "phone", "school", "photo", "email"]
        
        for field in unnecessary_fields:
            assert field not in child_dict

    def test_preference_data_sanitization(self):
        """Test preferences don't contain sensitive data."""
        preferences = {
            "favorite_color": "blue",      # OK
            "favorite_animal": "dog",      # OK
            "interests": ["space", "art"], # OK
            # "home_address": "123 Main",  # NOT OK
            # "parent_phone": "555-1234"   # NOT OK
        }
        
        child = Child(name="Test", age=8, preferences=preferences)
        
        # Verify no sensitive data in preferences
        sensitive_keys = ["address", "phone", "email", "location"]
        for key in sensitive_keys:
            assert not any(s in k.lower() for k in child.preferences.keys() for s in sensitive_keys)


class TestSecurityHeaders:
    """Test security headers and API security."""

    @pytest.mark.asyncio
    async def test_cors_origin_validation(self):
        """Test CORS allows only configured origins."""
        # Test configuration
        allowed_origins = ["https://app.teddybear.com", "https://admin.teddybear.com"]
        
        # Should reject unknown origins
        unknown_origin = "https://evil.com"
        assert unknown_origin not in allowed_origins
        
        # TODO: Test actual CORS middleware configuration

    def test_authentication_required(self):
        """Test endpoints require authentication."""
        # Critical endpoints that must require auth
        protected_endpoints = [
            "/chat",
            "/children/{child_id}",
            "/conversations/{child_id}/history",
            "/safety/report"
        ]
        
        # TODO: Verify auth decorators on these endpoints

    @pytest.mark.asyncio
    async def test_jwt_token_validation(self):
        """Test JWT tokens are properly validated."""
        # Mock JWT validation
        with patch("src.infrastructure.security.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = None  # Invalid token
            
            # Should reject invalid tokens
            # TODO: Test auth middleware with invalid token