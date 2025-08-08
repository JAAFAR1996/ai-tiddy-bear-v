"""
Unit tests for API documentation models.
Tests Pydantic models used for API documentation and examples.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from pydantic import ValidationError

from src.api.docs import (
    UserRole,
    ConversationMode,
    ParentRegistrationRequest,
    LoginRequest,
    AuthResponse,
    ChildProfileRequest,
    ChildProfileResponse,
    ConversationRequest,
    ConversationResponse,
    SafetyReport,
    HealthStatus,
    ErrorResponse,
)


class TestDocumentationEnums:
    """Test enum definitions in documentation models."""

    def test_user_role_enum_values(self):
        """Test UserRole enum has correct values."""
        assert UserRole.PARENT == "parent"
        assert UserRole.GUARDIAN == "guardian"
        assert UserRole.ADMIN == "admin"
        
        # Test string inheritance
        assert isinstance(UserRole.PARENT, str)

    def test_conversation_mode_enum_values(self):
        """Test ConversationMode enum has correct values."""
        assert ConversationMode.TEXT == "text"
        assert ConversationMode.VOICE == "voice"
        assert ConversationMode.MIXED == "mixed"
        
        # Test string inheritance
        assert isinstance(ConversationMode.TEXT, str)

    def test_enum_completeness(self):
        """Test all expected enum values exist."""
        user_roles = {role.value for role in UserRole}
        expected_roles = {"parent", "guardian", "admin"}
        assert user_roles == expected_roles
        
        conversation_modes = {mode.value for mode in ConversationMode}
        expected_modes = {"text", "voice", "mixed"}
        assert conversation_modes == expected_modes


class TestParentRegistrationRequestDocs:
    """Test ParentRegistrationRequest documentation model."""

    def test_valid_parent_registration_request(self):
        """Test valid parent registration request."""
        request = ParentRegistrationRequest(
            email="parent@example.com",
            password="SecureP@ssw0rd!",
            first_name="John",
            last_name="Doe",
            phone="+1234567890",
            consent_to_coppa=True,
            terms_accepted=True,
            marketing_consent=False,
        )
        
        assert request.email == "parent@example.com"
        assert request.password == "SecureP@ssw0rd!"
        assert request.first_name == "John"
        assert request.last_name == "Doe"
        assert request.phone == "+1234567890"
        assert request.consent_to_coppa is True
        assert request.terms_accepted is True
        assert request.marketing_consent is False

    def test_parent_registration_field_descriptions(self):
        """Test field descriptions are comprehensive."""
        model_schema = ParentRegistrationRequest.model_json_schema()
        properties = model_schema["properties"]
        
        # Check key fields have descriptions
        assert "description" in properties["email"]
        assert "verification" in properties["email"]["description"].lower()
        
        assert "description" in properties["password"]
        assert "8" in properties["password"]["description"]  # Minimum length
        
        assert "description" in properties["consent_to_coppa"]
        assert "coppa" in properties["consent_to_coppa"]["description"].lower()
        
        assert "description" in properties["terms_accepted"]
        assert "terms" in properties["terms_accepted"]["description"].lower()

    def test_parent_registration_schema_example(self):
        """Test schema example is complete and valid."""
        config = ParentRegistrationRequest.Config
        example = config.schema_extra["example"]
        
        # Verify example has all required fields
        required_fields = [
            "email", "password", "first_name", "last_name",
            "phone", "consent_to_coppa", "terms_accepted", "marketing_consent"
        ]
        
        for field in required_fields:
            assert field in example
        
        # Verify example creates valid model
        model = ParentRegistrationRequest(**example)
        assert model.email == example["email"]
        
        # Verify COPPA compliance in example
        assert example["consent_to_coppa"] is True
        assert example["terms_accepted"] is True

    def test_parent_registration_password_min_length(self):
        """Test password minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            ParentRegistrationRequest(
                email="parent@example.com",
                password="short",  # Less than 8 characters
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                consent_to_coppa=True,
                terms_accepted=True,
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)

    def test_parent_registration_required_fields(self):
        """Test all required fields are enforced."""
        required_fields = [
            "email", "password", "first_name", "last_name",
            "phone", "consent_to_coppa", "terms_accepted"
        ]
        
        for field in required_fields:
            data = {
                "email": "parent@example.com",
                "password": "SecureP@ssw0rd!",
                "first_name": "John",
                "last_name": "Doe",
                "phone": "+1234567890",
                "consent_to_coppa": True,
                "terms_accepted": True,
            }
            
            del data[field]  # Remove the required field
            
            with pytest.raises(ValidationError):
                ParentRegistrationRequest(**data)

    def test_parent_registration_marketing_consent_default(self):
        """Test marketing consent defaults to False."""
        request = ParentRegistrationRequest(
            email="parent@example.com",
            password="SecureP@ssw0rd!",
            first_name="John",
            last_name="Doe",
            phone="+1234567890",
            consent_to_coppa=True,
            terms_accepted=True,
            # marketing_consent not provided
        )
        
        assert request.marketing_consent is False


class TestLoginRequestDocs:
    """Test LoginRequest documentation model."""

    def test_valid_login_request(self):
        """Test valid login request."""
        request = LoginRequest(
            email="parent@example.com",
            password="SecureP@ssw0rd!",
            remember_me=True
        )
        
        assert request.email == "parent@example.com"
        assert request.password == "SecureP@ssw0rd!"
        assert request.remember_me is True

    def test_login_request_defaults(self):
        """Test login request default values."""
        request = LoginRequest(
            email="parent@example.com",
            password="SecureP@ssw0rd!"
        )
        
        assert request.remember_me is False

    def test_login_request_schema_example(self):
        """Test login request schema example."""
        config = LoginRequest.Config
        example = config.schema_extra["example"]
        
        # Verify example creates valid model
        model = LoginRequest(**example)
        assert model.email == example["email"]
        assert model.remember_me == example["remember_me"]

    def test_login_request_field_validation(self):
        """Test field validation."""
        model_schema = LoginRequest.model_json_schema()
        properties = model_schema["properties"]
        
        # Check examples are present
        assert properties["email"]["example"] == "parent@example.com"
        assert properties["password"]["example"] == "SecureP@ssw0rd!"
        
        # Check remember_me has description
        assert "description" in properties["remember_me"]
        assert "session" in properties["remember_me"]["description"].lower()


class TestAuthResponseDocs:
    """Test AuthResponse documentation model."""

    def test_valid_auth_response(self):
        """Test valid authentication response."""
        response = AuthResponse(
            access_token="eyJ0eXAiOiJKV1QiLCJhbGc...",
            refresh_token="eyJ0eXAiOiJKV1QiLCJhbGc...",
            expires_in=3600,
            user={
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "parent@example.com",
                "role": "parent",
            }
        )
        
        assert response.access_token == "eyJ0eXAiOiJKV1QiLCJhbGc..."
        assert response.refresh_token == "eyJ0eXAiOiJKV1QiLCJhbGc..."
        assert response.token_type == "Bearer"
        assert response.expires_in == 3600
        assert response.user["email"] == "parent@example.com"

    def test_auth_response_schema_example(self):
        """Test auth response schema example."""
        config = AuthResponse.Config
        example = config.schema_extra["example"]
        
        # Verify example creates valid model
        model = AuthResponse(**example)
        assert model.token_type == "Bearer"
        assert model.expires_in == 3600
        assert "verified" in model.user

    def test_auth_response_field_validation(self):
        """Test field validation and descriptions."""
        model_schema = AuthResponse.model_json_schema()
        properties = model_schema["properties"]
        
        # Check expires_in has description
        assert "description" in properties["expires_in"]
        assert "seconds" in properties["expires_in"]["description"].lower()
        
        # Check default token_type
        assert properties["token_type"]["default"] == "Bearer"


class TestChildProfileRequestDocs:
    """Test ChildProfileRequest documentation model."""

    def test_valid_child_profile_request(self):
        """Test valid child profile request."""
        request = ChildProfileRequest(
            name="Emma",
            age=7,
            interests=["dinosaurs", "space", "animals"],
            safety_level="high",
            language_preference="en",
            parental_controls={
                "conversation_time_limit": 30,
                "daily_interaction_limit": 60,
                "content_filtering": "strict",
                "voice_enabled": True,
            }
        )
        
        assert request.name == "Emma"
        assert request.age == 7
        assert "dinosaurs" in request.interests
        assert request.safety_level == "high"
        assert request.parental_controls["content_filtering"] == "strict"

    def test_child_profile_age_validation(self):
        """Test age validation constraints."""
        # Test minimum age
        with pytest.raises(ValidationError):
            ChildProfileRequest(
                name="Baby",
                age=1,  # Below minimum
                interests=["toys"]
            )
        
        # Test maximum age
        with pytest.raises(ValidationError):
            ChildProfileRequest(
                name="Teen",
                age=14,  # Above maximum
                interests=["music"]
            )

    @pytest.mark.parametrize("age", [2, 3, 7, 10, 13])
    def test_child_profile_valid_ages(self, age):
        """Test all valid ages are accepted."""
        request = ChildProfileRequest(
            name="Child",
            age=age,
            interests=["reading"]
        )
        assert request.age == age

    def test_child_profile_field_descriptions(self):
        """Test field descriptions are comprehensive."""
        model_schema = ChildProfileRequest.model_json_schema()
        properties = model_schema["properties"]
        
        # Check name description mentions privacy
        assert "privacy" in properties["name"]["description"].lower()
        
        # Check age description mentions COPPA
        assert "coppa" in properties["age"]["description"].lower()
        
        # Check interests description mentions personalization
        assert "personalized" in properties["interests"]["description"].lower()

    def test_child_profile_schema_example(self):
        """Test schema example is complete."""
        config = ChildProfileRequest.Config
        example = config.schema_extra["example"]
        
        # Verify example creates valid model
        model = ChildProfileRequest(**example)
        assert model.name == "Emma"
        assert model.age == 7
        assert len(model.interests) >= 3
        
        # Verify parental controls in example
        assert "conversation_time_limit" in example["parental_controls"]
        assert "content_filtering" in example["parental_controls"]

    def test_child_profile_defaults(self):
        """Test default values."""
        request = ChildProfileRequest(
            name="Emma",
            age=7,
            interests=["dinosaurs"]
        )
        
        # Check defaults
        assert request.language_preference == "en"
        assert isinstance(request.parental_controls, dict)


class TestChildProfileResponseDocs:
    """Test ChildProfileResponse documentation model."""

    def test_valid_child_profile_response(self):
        """Test valid child profile response."""
        now = datetime.now()
        
        response = ChildProfileResponse(
            id="550e8400-e29b-41d4-a716-446655440001",
            name="Emma",
            age=7,
            interests=["dinosaurs", "space"],
            safety_level="high",
            created_at=now,
            last_interaction=now,
            total_conversations=15
        )
        
        assert response.id == "550e8400-e29b-41d4-a716-446655440001"
        assert response.name == "Emma"
        assert response.total_conversations == 15

    def test_child_profile_response_optional_fields(self):
        """Test optional fields."""
        response = ChildProfileResponse(
            id="test-id",
            name="Emma",
            age=7,
            interests=["reading"],
            safety_level="high",
            created_at=datetime.now(),
            total_conversations=0
        )
        
        assert response.last_interaction is None

    def test_child_profile_response_schema_example(self):
        """Test schema example."""
        config = ChildProfileResponse.Config
        example = config.schema_extra["example"]
        
        # Should be able to create model from example
        # Note: datetime fields need to be converted
        example_copy = example.copy()
        example_copy["created_at"] = datetime.fromisoformat(example["created_at"].replace('Z', '+00:00'))
        if example["last_interaction"]:
            example_copy["last_interaction"] = datetime.fromisoformat(example["last_interaction"].replace('Z', '+00:00'))
        
        model = ChildProfileResponse(**example_copy)
        assert model.name == "Emma"
        assert model.total_conversations == 15


class TestConversationRequestDocs:
    """Test ConversationRequest documentation model."""

    def test_valid_conversation_request(self):
        """Test valid conversation request."""
        request = ConversationRequest(
            message="Hi Teddy! What's your favorite color?",
            conversation_id="550e8400-e29b-41d4-a716-446655440002",
            mode=ConversationMode.TEXT,
            voice_enabled=True,
            context={"emotion": "excited", "activity": "playing"}
        )
        
        assert request.message == "Hi Teddy! What's your favorite color?"
        assert request.conversation_id == "550e8400-e29b-41d4-a716-446655440002"
        assert request.mode == ConversationMode.TEXT
        assert request.voice_enabled is True
        assert request.context["emotion"] == "excited"

    def test_conversation_request_defaults(self):
        """Test default values."""
        request = ConversationRequest(
            message="Hello Teddy!"
        )
        
        assert request.conversation_id is None
        assert request.mode == ConversationMode.TEXT
        assert request.voice_enabled is False
        assert request.context is None

    def test_conversation_request_field_validation(self):
        """Test field validation and examples."""
        model_schema = ConversationRequest.model_json_schema()
        properties = model_schema["properties"]
        
        # Check message has example
        assert "example" in properties["message"]
        
        # Check conversation_id description
        assert "description" in properties["conversation_id"]
        assert "omit" in properties["conversation_id"]["description"].lower()
        
        # Check voice_enabled description
        assert "description" in properties["voice_enabled"]
        assert "voice" in properties["voice_enabled"]["description"].lower()

    def test_conversation_request_schema_example(self):
        """Test schema example."""
        config = ConversationRequest.Config
        example = config.schema_extra["example"]
        
        # Verify example creates valid model
        model = ConversationRequest(**example)
        assert "dinosaurs" in model.message
        assert model.mode == "text"
        assert model.voice_enabled is True


class TestConversationResponseDocs:
    """Test ConversationResponse documentation model."""

    def test_valid_conversation_response(self):
        """Test valid conversation response."""
        response = ConversationResponse(
            conversation_id="550e8400-e29b-41d4-a716-446655440002",
            message="Hi Emma! I love talking about dinosaurs!",
            audio_url="https://api.aiteddybear.com/audio/response_123.mp3",
            safety_score=1.0,
            educational_value="paleontology_basics",
            suggested_followups=["What did Triceratops eat?", "How big were dinosaurs?"],
            interaction_metadata={
                "response_time_ms": 750,
                "content_filtered": False,
                "educational_tags": ["science", "prehistory"],
            }
        )
        
        assert "dinosaurs" in response.message
        assert response.safety_score == 1.0
        assert len(response.suggested_followups) == 2
        assert response.interaction_metadata["response_time_ms"] == 750

    def test_conversation_response_defaults(self):
        """Test default values."""
        response = ConversationResponse(
            conversation_id="test-id",
            message="Hello there!",
            safety_score=0.95
        )
        
        assert response.audio_url is None
        assert response.educational_value is None
        assert response.suggested_followups == []
        assert response.interaction_metadata == {}

    def test_conversation_response_schema_example(self):
        """Test schema example."""
        config = ConversationResponse.Config
        example = config.schema_extra["example"]
        
        # Verify example creates valid model
        model = ConversationResponse(**example)
        assert "Triceratops" in model.message
        assert model.safety_score == 1.0
        assert len(model.suggested_followups) == 3


class TestSafetyReportDocs:
    """Test SafetyReport documentation model."""

    def test_valid_safety_report(self):
        """Test valid safety report."""
        timestamp = datetime.now()
        
        report = SafetyReport(
            incident_type="inappropriate_content",
            severity="medium",
            description="Child attempted to share personal information",
            action_taken="content_blocked_and_redirected",
            timestamp=timestamp
        )
        
        assert report.incident_type == "inappropriate_content"
        assert report.severity == "medium"
        assert "personal information" in report.description
        assert report.action_taken == "content_blocked_and_redirected"
        assert report.timestamp == timestamp

    def test_safety_report_schema_example(self):
        """Test safety report schema example."""
        config = SafetyReport.Config
        example = config.schema_extra["example"]
        
        # Should contain safety-related information
        assert "inappropriate" in example["incident_type"]
        assert "medium" == example["severity"]
        assert "content" in example["description"].lower()
        assert "blocked" in example["action_taken"]

    def test_safety_report_field_examples(self):
        """Test field examples are appropriate."""
        model_schema = SafetyReport.model_json_schema()
        properties = model_schema["properties"]
        
        # All fields should have examples
        for field in ["incident_type", "severity", "description", "action_taken"]:
            assert "example" in properties[field]


class TestHealthStatusDocs:
    """Test HealthStatus documentation model."""

    def test_valid_health_status(self):
        """Test valid health status."""
        status = HealthStatus(
            status="healthy",
            version="1.0.0",
            uptime=86400,
            active_conversations=42,
            safety_checks_passed=1250
        )
        
        assert status.status == "healthy"
        assert status.version == "1.0.0"
        assert status.uptime == 86400
        assert status.active_conversations == 42
        assert status.safety_checks_passed == 1250

    def test_health_status_field_descriptions(self):
        """Test field descriptions."""
        model_schema = HealthStatus.model_json_schema()
        properties = model_schema["properties"]
        
        # Check uptime has description
        assert "description" in properties["uptime"]
        assert "seconds" in properties["uptime"]["description"].lower()

    def test_health_status_schema_example(self):
        """Test schema example."""
        config = HealthStatus.Config
        example = config.schema_extra["example"]
        
        # Verify example creates valid model
        model = HealthStatus(**example)
        assert model.status == "healthy"
        assert model.uptime > 0
        assert model.safety_checks_passed > 0


class TestErrorResponseDocs:
    """Test ErrorResponse documentation model."""

    def test_valid_error_response(self):
        """Test valid error response."""
        error = ErrorResponse(
            error={
                "code": "VALIDATION_ERROR",
                "message": "Invalid input data",
                "field": "age",
                "correlation_id": "req_abc123",
            }
        )
        
        assert error.error["code"] == "VALIDATION_ERROR"
        assert error.error["message"] == "Invalid input data"
        assert error.error["field"] == "age"
        assert error.error["correlation_id"] == "req_abc123"

    def test_error_response_schema_example(self):
        """Test error response schema example."""
        config = ErrorResponse.Config
        example = config.schema_extra["example"]
        
        # Verify example creates valid model
        model = ErrorResponse(**example)
        assert model.error["code"] == "VALIDATION_ERROR"
        assert "coppa" in model.error["message"].lower()

    def test_error_response_field_structure(self):
        """Test error field structure."""
        model_schema = ErrorResponse.model_json_schema()
        properties = model_schema["properties"]
        
        # Check error field example
        error_example = properties["error"]["example"]
        assert "code" in error_example
        assert "message" in error_example
        assert "correlation_id" in error_example


class TestModelConsistency:
    """Test consistency between documentation models."""

    def test_enum_consistency(self):
        """Test enums are consistent across models."""
        # UserRole should be used consistently
        assert UserRole.PARENT == "parent"
        assert UserRole.GUARDIAN == "guardian"
        assert UserRole.ADMIN == "admin"
        
        # ConversationMode should be used consistently  
        assert ConversationMode.TEXT == "text"
        assert ConversationMode.VOICE == "voice"
        assert ConversationMode.MIXED == "mixed"

    def test_example_consistency(self):
        """Test examples are consistent across related models."""
        # Parent registration and login should use same email format
        reg_config = ParentRegistrationRequest.Config
        login_config = LoginRequest.Config
        
        reg_email = reg_config.schema_extra["example"]["email"]
        login_email = login_config.schema_extra["example"]["email"]
        
        # Should both be valid email formats
        assert "@" in reg_email
        assert "@" in login_email

    def test_field_naming_consistency(self):
        """Test field names are consistent across models."""
        # Child-related models should use consistent field names
        child_request_schema = ChildProfileRequest.model_json_schema()
        child_response_schema = ChildProfileResponse.model_json_schema()
        
        # Common fields should have same names
        common_fields = ["name", "age", "interests", "safety_level"]
        
        for field in common_fields:
            assert field in child_request_schema["properties"]
            assert field in child_response_schema["properties"]

    def test_datetime_format_consistency(self):
        """Test datetime formats are consistent."""
        # All datetime examples should use ISO format
        models_with_datetime = [
            ChildProfileResponse,
            SafetyReport,
        ]
        
        for model_class in models_with_datetime:
            schema = model_class.model_json_schema()
            properties = schema["properties"]
            
            for field_name, field_info in properties.items():
                if field_info.get("type") == "string" and field_info.get("format") == "date-time":
                    if "example" in field_info:
                        example = field_info["example"]
                        # Should contain T for ISO format
                        assert "T" in str(example) or example is None