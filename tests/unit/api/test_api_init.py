"""
Unit tests for API module initialization and models.
Tests Pydantic models, enums, OpenAPI schema generation, and validation.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError
from fastapi import FastAPI

from src.api import (
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
    tags_metadata,
    custom_openapi_schema,
)


class TestEnums:
    """Test enum definitions and values."""

    def test_user_role_enum_values(self):
        """Test UserRole enum has correct values."""
        assert UserRole.PARENT == "parent"
        assert UserRole.GUARDIAN == "guardian"
        assert UserRole.ADMIN == "admin"
        
        # Test all enum members exist
        expected_roles = {"parent", "guardian", "admin"}
        actual_roles = {role.value for role in UserRole}
        assert actual_roles == expected_roles

    def test_conversation_mode_enum_values(self):
        """Test ConversationMode enum has correct values."""
        assert ConversationMode.TEXT == "text"
        assert ConversationMode.VOICE == "voice"
        assert ConversationMode.MIXED == "mixed"
        
        # Test all enum members exist
        expected_modes = {"text", "voice", "mixed"}
        actual_modes = {mode.value for mode in ConversationMode}
        assert actual_modes == expected_modes

    def test_enum_string_inheritance(self):
        """Test enums inherit from str for JSON serialization."""
        assert isinstance(UserRole.PARENT, str)
        assert isinstance(ConversationMode.TEXT, str)


class TestParentRegistrationRequest:
    """Test ParentRegistrationRequest model."""

    def test_valid_parent_registration(self):
        """Test valid parent registration data."""
        data = {
            "email": "parent@example.com",
            "password": "SecureP@ssw0rd!",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
            "consent_to_coppa": True,
            "terms_accepted": True,
            "marketing_consent": False,
        }
        
        request = ParentRegistrationRequest(**data)
        
        assert request.email == "parent@example.com"
        assert request.password == "SecureP@ssw0rd!"
        assert request.first_name == "John"
        assert request.last_name == "Doe"
        assert request.phone == "+1234567890"
        assert request.consent_to_coppa is True
        assert request.terms_accepted is True
        assert request.marketing_consent is False

    def test_parent_registration_with_marketing_consent(self):
        """Test parent registration with marketing consent enabled."""
        data = {
            "email": "parent@example.com",
            "password": "SecurePassword123!",
            "first_name": "Jane",
            "last_name": "Smith",
            "phone": "+1987654321",
            "consent_to_coppa": True,
            "terms_accepted": True,
            "marketing_consent": True,
        }
        
        request = ParentRegistrationRequest(**data)
        assert request.marketing_consent is True

    def test_parent_registration_missing_required_fields(self):
        """Test parent registration fails with missing required fields."""
        # Missing email
        with pytest.raises(ValidationError):
            ParentRegistrationRequest(
                password="SecureP@ssw0rd!",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                consent_to_coppa=True,
                terms_accepted=True,
            )

    def test_parent_registration_short_password(self):
        """Test parent registration fails with short password."""
        data = {
            "email": "parent@example.com",
            "password": "short",  # Less than 8 characters
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
            "consent_to_coppa": True,
            "terms_accepted": True,
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ParentRegistrationRequest(**data)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)

    def test_parent_registration_schema_example(self):
        """Test the schema example matches expected format."""
        config = ParentRegistrationRequest.Config
        example = config.schema_extra["example"]
        
        # Verify example contains all required fields
        required_fields = [
            "email", "password", "first_name", "last_name", 
            "phone", "consent_to_coppa", "terms_accepted", "marketing_consent"
        ]
        
        for field in required_fields:
            assert field in example
        
        # Verify COPPA compliance fields are True in example
        assert example["consent_to_coppa"] is True
        assert example["terms_accepted"] is True


class TestLoginRequest:
    """Test LoginRequest model."""

    def test_valid_login_request(self):
        """Test valid login request data."""
        request = LoginRequest(
            email="parent@example.com",
            password="SecureP@ssw0rd!",
            remember_me=True
        )
        
        assert request.email == "parent@example.com"
        assert request.password == "SecureP@ssw0rd!"
        assert request.remember_me is True

    def test_login_request_default_remember_me(self):
        """Test login request with default remember_me value."""
        request = LoginRequest(
            email="parent@example.com",
            password="SecureP@ssw0rd!"
        )
        
        assert request.remember_me is False

    def test_login_request_missing_fields(self):
        """Test login request fails with missing required fields."""
        # Missing password
        with pytest.raises(ValidationError):
            LoginRequest(email="parent@example.com")
        
        # Missing email
        with pytest.raises(ValidationError):
            LoginRequest(password="SecureP@ssw0rd!")


class TestAuthResponse:
    """Test AuthResponse model."""

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
        assert response.token_type == "Bearer"  # Default value
        assert response.expires_in == 3600
        assert response.user["email"] == "parent@example.com"

    def test_auth_response_default_token_type(self):
        """Test default token type is Bearer."""
        response = AuthResponse(
            access_token="token",
            refresh_token="refresh",
            expires_in=3600,
            user={"id": "123"}
        )
        
        assert response.token_type == "Bearer"


class TestChildProfileRequest:
    """Test ChildProfileRequest model."""

    def test_valid_child_profile_request(self):
        """Test valid child profile creation request."""
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
        assert request.language_preference == "en"
        assert request.parental_controls["content_filtering"] == "strict"

    def test_child_profile_request_defaults(self):
        """Test child profile request with default values."""
        request = ChildProfileRequest(
            name="Emma",
            age=7,
            interests=["dinosaurs"]
        )
        
        # Should use default safety level
        assert hasattr(request, 'safety_level')
        assert request.language_preference == "en"
        assert isinstance(request.parental_controls, dict)

    def test_child_profile_age_validation_too_young(self):
        """Test child profile fails with age too young."""
        with pytest.raises(ValidationError) as exc_info:
            ChildProfileRequest(
                name="Baby",
                age=1,  # Below minimum age of 2
                interests=["toys"]
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("age",) for error in errors)

    def test_child_profile_age_validation_too_old(self):
        """Test child profile fails with age too old."""
        with pytest.raises(ValidationError) as exc_info:
            ChildProfileRequest(
                name="Teen",
                age=14,  # Above maximum age of 13
                interests=["music"]
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("age",) for error in errors)

    @pytest.mark.parametrize("age", [2, 5, 8, 10, 13])
    def test_child_profile_valid_ages(self, age):
        """Test child profile accepts all valid ages."""
        request = ChildProfileRequest(
            name="Child",
            age=age,
            interests=["reading"]
        )
        assert request.age == age


class TestChildProfileResponse:
    """Test ChildProfileResponse model."""

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
        assert response.age == 7
        assert response.interests == ["dinosaurs", "space"]
        assert response.safety_level == "high"
        assert response.created_at == now
        assert response.last_interaction == now
        assert response.total_conversations == 15

    def test_child_profile_response_optional_last_interaction(self):
        """Test child profile response with no last interaction."""
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


class TestConversationRequest:
    """Test ConversationRequest model."""

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
        """Test conversation request with default values."""
        request = ConversationRequest(
            message="Hello Teddy!"
        )
        
        assert request.conversation_id is None
        assert request.mode == ConversationMode.TEXT
        assert request.voice_enabled is False
        assert request.context is None

    def test_conversation_request_with_string_mode(self):
        """Test conversation request accepts string mode."""
        request = ConversationRequest(
            message="Hello",
            mode="voice"  # String instead of enum
        )
        
        assert request.mode == ConversationMode.VOICE


class TestConversationResponse:
    """Test ConversationResponse model."""

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
        
        assert response.conversation_id == "550e8400-e29b-41d4-a716-446655440002"
        assert "dinosaurs" in response.message
        assert response.audio_url is not None
        assert response.safety_score == 1.0
        assert response.educational_value == "paleontology_basics"
        assert len(response.suggested_followups) == 2
        assert response.interaction_metadata["response_time_ms"] == 750

    def test_conversation_response_defaults(self):
        """Test conversation response with default values."""
        response = ConversationResponse(
            conversation_id="test-id",
            message="Hello there!",
            safety_score=0.95
        )
        
        assert response.audio_url is None
        assert response.educational_value is None
        assert response.suggested_followups == []
        assert response.interaction_metadata == {}


class TestSafetyReport:
    """Test SafetyReport model."""

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


class TestHealthStatus:
    """Test HealthStatus model."""

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


class TestErrorResponse:
    """Test ErrorResponse model."""

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


class TestTagsMetadata:
    """Test OpenAPI tags metadata."""

    def test_tags_metadata_structure(self):
        """Test tags metadata has correct structure."""
        assert isinstance(tags_metadata, list)
        assert len(tags_metadata) > 0
        
        # Check each tag has required fields
        for tag in tags_metadata:
            assert "name" in tag
            assert "description" in tag
            assert isinstance(tag["name"], str)
            assert isinstance(tag["description"], str)

    def test_tags_metadata_completeness(self):
        """Test all expected tags are present."""
        tag_names = {tag["name"] for tag in tags_metadata}
        expected_tags = {
            "Authentication", "Children", "Conversations", 
            "Safety", "Health", "Admin"
        }
        
        assert tag_names == expected_tags

    def test_tags_metadata_descriptions(self):
        """Test tag descriptions contain key information."""
        tag_dict = {tag["name"]: tag["description"] for tag in tags_metadata}
        
        # Authentication should mention JWT and security
        auth_desc = tag_dict["Authentication"].lower()
        assert "jwt" in auth_desc
        assert "authentication" in auth_desc
        
        # Children should mention COPPA
        children_desc = tag_dict["Children"].lower()
        assert "coppa" in children_desc
        assert "privacy" in children_desc or "child" in children_desc
        
        # Safety should mention monitoring
        safety_desc = tag_dict["Safety"].lower()
        assert "safety" in safety_desc
        assert "monitoring" in safety_desc or "content" in safety_desc


class TestCustomOpenAPISchema:
    """Test custom OpenAPI schema generation."""

    def test_custom_openapi_schema_with_existing_schema(self):
        """Test custom schema returns existing schema if available."""
        app = Mock(spec=FastAPI)
        existing_schema = {"openapi": "3.0.3", "info": {"title": "Test"}}
        app.openapi_schema = existing_schema
        
        result = custom_openapi_schema(app)
        
        assert result == existing_schema

    @patch('src.api.get_openapi')
    def test_custom_openapi_schema_generation(self, mock_get_openapi):
        """Test custom schema generation for new app."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.title = "Test App"
        app.version = "1.0.0"
        app.description = "Test Description"
        app.routes = []
        
        mock_fastapi_schema = {
            "paths": {"/test": {}},
            "components": {"schemas": {"TestModel": {}}}
        }
        mock_get_openapi.return_value = mock_fastapi_schema
        
        result = custom_openapi_schema(app)
        
        # Check basic structure
        assert result["openapi"] == "3.0.3"
        assert result["info"]["title"] == "AI Teddy Bear API"
        assert result["info"]["version"] == "1.0.0"
        
        # Check servers are defined
        assert "servers" in result
        assert len(result["servers"]) == 3
        
        # Check security scheme
        assert "components" in result
        assert "securitySchemes" in result["components"]
        assert "BearerAuth" in result["components"]["securitySchemes"]
        
        # Check tags
        assert result["tags"] == tags_metadata
        
        # Check paths from FastAPI are merged
        assert result["paths"] == mock_fastapi_schema["paths"]
        
        # Verify schema was set on app
        assert app.openapi_schema == result

    def test_custom_openapi_schema_info_section(self):
        """Test the info section of custom schema."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.title = "Test"
        app.version = "1.0.0"
        app.description = "Test"
        app.routes = []
        
        with patch('src.api.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        info = result["info"]
        
        # Check required fields
        assert info["title"] == "AI Teddy Bear API"
        assert info["version"] == "1.0.0"
        assert "description" in info
        assert "contact" in info
        assert "license" in info
        assert "termsOfService" in info
        
        # Check contact information
        contact = info["contact"]
        assert contact["name"] == "AI Teddy Bear Support Team"
        assert "support@aiteddybear.com" in contact["email"]
        
        # Check description contains key information
        description = info["description"].lower()
        assert "coppa" in description
        assert "child" in description
        assert "safety" in description

    def test_custom_openapi_schema_servers(self):
        """Test server configuration in schema."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.title = "Test"
        app.version = "1.0.0"
        app.description = "Test"
        app.routes = []
        
        with patch('src.api.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        servers = result["servers"]
        server_urls = [server["url"] for server in servers]
        
        assert "https://api.aiteddybear.com" in server_urls
        assert "https://staging-api.aiteddybear.com" in server_urls
        assert "http://localhost:8000" in server_urls

    def test_custom_openapi_schema_security(self):
        """Test security configuration in schema."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.title = "Test"
        app.version = "1.0.0"
        app.description = "Test"
        app.routes = []
        
        with patch('src.api.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        # Check security schemes
        security_schemes = result["components"]["securitySchemes"]
        bearer_auth = security_schemes["BearerAuth"]
        
        assert bearer_auth["type"] == "http"
        assert bearer_auth["scheme"] == "bearer"
        assert bearer_auth["bearerFormat"] == "JWT"
        
        # Check global security
        assert result["security"] == [{"BearerAuth": []}]

    @patch('src.api.get_openapi')
    def test_custom_openapi_schema_components_merge(self, mock_get_openapi):
        """Test that FastAPI components are properly merged."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.title = "Test"
        app.version = "1.0.0"
        app.description = "Test"
        app.routes = []
        
        fastapi_components = {
            "components": {
                "schemas": {
                    "UserModel": {"type": "object"},
                    "ResponseModel": {"type": "object"}
                }
            }
        }
        mock_get_openapi.return_value = fastapi_components
        
        result = custom_openapi_schema(app)
        
        schemas = result["components"]["schemas"]
        
        # Should have our custom ErrorResponse schema
        assert "ErrorResponse" in schemas
        
        # Should have FastAPI's schemas
        assert "UserModel" in schemas
        assert "ResponseModel" in schemas


class TestModelIntegration:
    """Test model integration and edge cases."""

    def test_model_serialization(self):
        """Test models can be serialized to JSON."""
        request = ParentRegistrationRequest(
            email="test@example.com",
            password="SecureP@ssw0rd!",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            consent_to_coppa=True,
            terms_accepted=True
        )
        
        json_data = request.model_dump_json()
        assert isinstance(json_data, str)
        assert "test@example.com" in json_data

    def test_model_from_dict(self):
        """Test models can be created from dictionaries."""
        data = {
            "email": "test@example.com",
            "password": "SecureP@ssw0rd!",
            "first_name": "Test",
            "last_name": "User",
            "phone": "+1234567890",
            "consent_to_coppa": True,
            "terms_accepted": True
        }
        
        request = ParentRegistrationRequest(**data)
        assert request.email == "test@example.com"
        assert request.consent_to_coppa is True

    def test_child_profile_with_empty_interests(self):
        """Test child profile with empty interests list."""
        request = ChildProfileRequest(
            name="Emma",
            age=7,
            interests=[]  # Empty list
        )
        
        assert request.interests == []

    def test_conversation_with_unicode_content(self):
        """Test conversation models handle unicode content."""
        request = ConversationRequest(
            message="Hello! 🧸 How are you today? ❤️"
        )
        
        assert "🧸" in request.message
        assert "❤️" in request.message