"""
Unit tests for OpenAPI configuration module.
Tests custom OpenAPI schema generation, tags metadata, and documentation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
from fastapi import FastAPI

from src.api.openapi_config import (
    tags_metadata,
    custom_openapi_schema,
    get_openapi_tags,
)


class TestTagsMetadata:
    """Test OpenAPI tags metadata configuration."""

    def test_tags_metadata_structure(self):
        """Test tags metadata has correct structure."""
        assert isinstance(tags_metadata, list)
        assert len(tags_metadata) > 0
        
        # Each tag should have required fields
        for tag in tags_metadata:
            assert "name" in tag
            assert "description" in tag
            assert isinstance(tag["name"], str)
            assert isinstance(tag["description"], str)
            assert len(tag["name"]) > 0
            assert len(tag["description"]) > 0

    def test_tags_metadata_completeness(self):
        """Test all expected tags are present."""
        tag_names = {tag["name"] for tag in tags_metadata}
        expected_tags = {
            "Authentication", "Children", "Conversations", 
            "Safety", "Health", "Admin"
        }
        
        assert tag_names == expected_tags

    def test_authentication_tag_content(self):
        """Test Authentication tag has proper content."""
        auth_tag = next(tag for tag in tags_metadata if tag["name"] == "Authentication")
        
        description = auth_tag["description"].lower()
        assert "jwt" in description
        assert "authentication" in description
        assert "security" in description
        assert "rate limiting" in description
        
        # Should have external docs
        assert "externalDocs" in auth_tag
        assert "url" in auth_tag["externalDocs"]
        assert "description" in auth_tag["externalDocs"]

    def test_children_tag_coppa_compliance(self):
        """Test Children tag emphasizes COPPA compliance."""
        children_tag = next(tag for tag in tags_metadata if tag["name"] == "Children")
        
        description = children_tag["description"].lower()
        assert "coppa" in description
        assert "privacy" in description or "child" in description
        assert "encryption" in description
        assert "consent" in description

    def test_conversations_tag_safety_focus(self):
        """Test Conversations tag emphasizes safety."""
        conv_tag = next(tag for tag in tags_metadata if tag["name"] == "Conversations")
        
        description = conv_tag["description"].lower()
        assert "safety" in description
        assert "monitoring" in description
        assert "age-appropriate" in description
        assert "educational" in description

    def test_safety_tag_monitoring_features(self):
        """Test Safety tag highlights monitoring features."""
        safety_tag = next(tag for tag in tags_metadata if tag["name"] == "Safety")
        
        description = safety_tag["description"].lower()
        assert "monitoring" in description
        assert "content" in description or "filtering" in description
        assert "incident" in description
        assert "parental" in description

    def test_health_tag_simplicity(self):
        """Test Health tag is appropriately simple."""
        health_tag = next(tag for tag in tags_metadata if tag["name"] == "Health")
        
        description = health_tag["description"].lower()
        assert "health" in description
        assert "monitoring" in description
        assert len(description) < 500  # Should be concise

    def test_admin_tag_restrictions(self):
        """Test Admin tag mentions access restrictions."""
        admin_tag = next(tag for tag in tags_metadata if tag["name"] == "Admin")
        
        description = admin_tag["description"].lower()
        assert "admin" in description or "administrator" in description
        assert "protected" in description or "management" in description


class TestGetOpenAPITags:
    """Test get_openapi_tags function."""

    def test_get_openapi_tags_returns_metadata(self):
        """Test function returns the tags metadata."""
        result = get_openapi_tags()
        assert result == tags_metadata
        assert isinstance(result, list)

    def test_get_openapi_tags_immutability(self):
        """Test function returns consistent data."""
        result1 = get_openapi_tags()
        result2 = get_openapi_tags()
        
        assert result1 == result2
        assert result1 is tags_metadata  # Should return same reference


class TestCustomOpenAPISchema:
    """Test custom OpenAPI schema generation."""

    def test_custom_openapi_schema_with_existing_schema(self):
        """Test returns existing schema if already set."""
        app = Mock(spec=FastAPI)
        existing_schema = {"openapi": "3.0.3", "info": {"title": "Existing"}}
        app.openapi_schema = existing_schema
        
        result = custom_openapi_schema(app)
        
        assert result == existing_schema
        assert result is existing_schema

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_generation(self, mock_get_openapi):
        """Test custom schema generation for new app."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        mock_fastapi_schema = {
            "openapi": "3.0.3",
            "info": {"title": "Test"},
            "paths": {"/test": {"get": {}}},
            "components": {"schemas": {"TestModel": {}}}
        }
        mock_get_openapi.return_value = mock_fastapi_schema
        
        result = custom_openapi_schema(app)
        
        # Verify mock was called correctly
        mock_get_openapi.assert_called_once_with(
            title="AI Teddy Bear API",
            version="1.0.0",
            description="Child-safe AI conversations with enterprise security",
            routes=app.routes,
            tags=tags_metadata
        )
        
        # Verify result structure
        assert result["openapi"] == "3.0.3"
        assert result["info"]["title"] == "AI Teddy Bear API"
        assert result["info"]["version"] == "1.0.0"
        
        # Schema should be set on app
        assert app.openapi_schema == result

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_info_section(self, mock_get_openapi):
        """Test the info section of custom schema."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        mock_get_openapi.return_value = {"paths": {}}
        
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
        assert "aiteddybear.com" in contact["url"]
        
        # Check description contains key information
        description = info["description"].lower()
        assert "coppa" in description
        assert "child" in description
        assert "safety" in description
        assert "🧸" in info["description"]  # Should have emoji

    def test_custom_openapi_schema_description_content(self):
        """Test description contains all required sections."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        with patch('src.api.openapi_config.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        description = result["info"]["description"]
        
        # Should contain major sections
        assert "## Overview" in description
        assert "## Key Features" in description
        assert "## Quick Start" in description
        assert "## Authentication" in description
        assert "## Rate Limiting" in description
        assert "## COPPA Compliance" in description
        assert "## Error Handling" in description
        assert "## Support" in description
        
        # Should contain curl examples
        assert "curl -X POST" in description
        assert "Authorization: Bearer" in description

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_servers(self, mock_get_openapi):
        """Test server configuration in schema."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        mock_get_openapi.return_value = {"paths": {}}
        
        result = custom_openapi_schema(app)
        
        servers = result["servers"]
        server_urls = [server["url"] for server in servers]
        
        assert "https://api.aiteddybear.com" in server_urls
        assert "https://staging-api.aiteddybear.com" in server_urls
        assert "http://localhost:8000" in server_urls
        
        # Check server descriptions
        server_descriptions = [server["description"] for server in servers]
        assert "Production Server" in server_descriptions
        assert "Staging Server" in server_descriptions
        assert "Development Server" in server_descriptions

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_security(self, mock_get_openapi):
        """Test security configuration in schema."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        mock_get_openapi.return_value = {"paths": {}}
        
        result = custom_openapi_schema(app)
        
        # Check security schemes
        security_schemes = result["components"]["securitySchemes"]
        bearer_auth = security_schemes["BearerAuth"]
        
        assert bearer_auth["type"] == "http"
        assert bearer_auth["scheme"] == "bearer"
        assert bearer_auth["bearerFormat"] == "JWT"
        assert "JWT token" in bearer_auth["description"]
        
        # Check global security requirement
        assert result["security"] == [{"BearerAuth": []}]

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_error_response(self, mock_get_openapi):
        """Test custom error response schema."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        mock_get_openapi.return_value = {"paths": {}}
        
        result = custom_openapi_schema(app)
        
        # Check error response schema
        schemas = result["components"]["schemas"]
        error_schema = schemas["ErrorResponse"]
        
        assert error_schema["type"] == "object"
        assert "error" in error_schema["properties"]
        
        error_props = error_schema["properties"]["error"]["properties"]
        assert "code" in error_props
        assert "message" in error_props
        assert "field" in error_props
        assert "correlation_id" in error_props
        
        # Check examples
        assert error_props["code"]["example"] == "VALIDATION_ERROR"
        assert error_props["message"]["example"] == "Invalid input data"

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_components_initialization(self, mock_get_openapi):
        """Test components section is properly initialized."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        # Test with no components in FastAPI schema
        mock_get_openapi.return_value = {"paths": {}}
        
        result = custom_openapi_schema(app)
        
        assert "components" in result
        assert "securitySchemes" in result["components"]
        assert "schemas" in result["components"]
        assert "ErrorResponse" in result["components"]["schemas"]

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_with_existing_components(self, mock_get_openapi):
        """Test schema merges with existing FastAPI components."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        fastapi_schema = {
            "paths": {"/test": {}},
            "components": {
                "schemas": {
                    "UserModel": {"type": "object"},
                    "ResponseModel": {"type": "object"}
                }
            }
        }
        mock_get_openapi.return_value = fastapi_schema
        
        result = custom_openapi_schema(app)
        
        schemas = result["components"]["schemas"]
        
        # Should have our custom schema
        assert "ErrorResponse" in schemas
        
        # Should have FastAPI's schemas (note: they may not be present if get_openapi doesn't return them)
        # The actual merge behavior depends on get_openapi implementation
        if "UserModel" in fastapi_schema["components"]["schemas"]:
            assert "UserModel" in schemas


class TestOpenAPISchemaIntegration:
    """Test integration aspects of OpenAPI schema."""

    def test_schema_consistency_with_tags(self):
        """Test schema uses consistent tags."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        with patch('src.api.openapi_config.get_openapi') as mock_get_openapi:
            mock_get_openapi.return_value = {"paths": {}}
            
            custom_openapi_schema(app)
            
            # Verify get_openapi was called with our tags
            call_args = mock_get_openapi.call_args
            assert call_args[1]["tags"] == tags_metadata

    def test_schema_coppa_compliance_emphasis(self):
        """Test schema emphasizes COPPA compliance throughout."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        with patch('src.api.openapi_config.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        # COPPA should be mentioned in multiple places
        full_schema_text = str(result).lower()
        coppa_count = full_schema_text.count("coppa")
        assert coppa_count >= 3  # Should appear multiple times
        
        # Child safety should be emphasized
        assert "child" in full_schema_text
        assert "safety" in full_schema_text

    def test_schema_educational_focus(self):
        """Test schema emphasizes educational aspects."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        with patch('src.api.openapi_config.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        description = result["info"]["description"].lower()
        assert "educational" in description
        assert "learning" in description
        assert "curiosity" in description or "education" in description

    def test_schema_security_emphasis(self):
        """Test schema emphasizes security features."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        with patch('src.api.openapi_config.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        description = result["info"]["description"].lower()
        assert "encryption" in description
        assert "security" in description
        assert "authentication" in description
        assert "rate limiting" in description

    def test_schema_production_readiness(self):
        """Test schema indicates production readiness."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        with patch('src.api.openapi_config.get_openapi', return_value={"paths": {}}):
            result = custom_openapi_schema(app)
        
        description = result["info"]["description"]
        assert "production" in description.lower()
        assert "99.9%" in description or "uptime" in description.lower()
        assert "enterprise" in description.lower()


class TestOpenAPISchemaEdgeCases:
    """Test edge cases and error conditions."""

    def test_custom_openapi_schema_with_none_routes(self):
        """Test schema generation with None routes."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = None
        
        with patch('src.api.openapi_config.get_openapi', return_value={"paths": {}}) as mock_get_openapi:
            result = custom_openapi_schema(app)
            
            # Should handle None routes gracefully
            call_args = mock_get_openapi.call_args
            assert call_args[1]["routes"] is None
            assert result is not None

    def test_custom_openapi_schema_with_empty_fastapi_response(self):
        """Test schema generation with minimal FastAPI response."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        with patch('src.api.openapi_config.get_openapi', return_value={}):
            result = custom_openapi_schema(app)
            
            # Should still create valid schema
            assert result["info"]["title"] == "AI Teddy Bear API"
            assert "components" in result
            assert "ErrorResponse" in result["components"]["schemas"]

    @patch('src.api.openapi_config.get_openapi')
    def test_custom_openapi_schema_sets_on_app(self, mock_get_openapi):
        """Test that generated schema is set on the app."""
        app = Mock(spec=FastAPI)
        app.openapi_schema = None
        app.routes = []
        
        mock_get_openapi.return_value = {"paths": {}}
        
        result = custom_openapi_schema(app)
        
        # Schema should be set on app for caching
        assert app.openapi_schema == result
        assert app.openapi_schema is result


class TestTagsMetadataValidation:
    """Test validation of tags metadata content."""

    def test_all_tags_have_security_mentions(self):
        """Test that security-related tags mention security features."""
        security_tags = ["Authentication", "Children", "Safety"]
        
        for tag_name in security_tags:
            tag = next(tag for tag in tags_metadata if tag["name"] == tag_name)
            description = tag["description"].lower()
            
            # Should mention some security concept
            security_keywords = [
                "security", "safe", "protection", "encrypt", 
                "monitor", "auth", "privacy", "compliance"
            ]
            assert any(keyword in description for keyword in security_keywords), \
                f"Tag {tag_name} should mention security concepts"

    def test_tags_avoid_technical_jargon(self):
        """Test that tag descriptions are accessible."""
        technical_terms = ["api", "endpoint", "http", "json", "rest"]
        
        for tag in tags_metadata:
            description = tag["description"].lower()
            
            # Should focus on features, not technical implementation
            jargon_count = sum(1 for term in technical_terms if term in description)
            total_words = len(description.split())
            
            # Less than 5% technical terms
            assert jargon_count / total_words < 0.05, \
                f"Tag {tag['name']} has too much technical jargon"

    def test_tags_emphasize_child_safety(self):
        """Test that child-related tags emphasize safety."""
        child_related_tags = ["Children", "Conversations", "Safety"]
        
        for tag_name in child_related_tags:
            tag = next(tag for tag in tags_metadata if tag["name"] == tag_name)
            description = tag["description"].lower()
            
            child_safety_keywords = [
                "child", "coppa", "safety", "age", "parent", 
                "monitor", "appropriate", "privacy"
            ]
            matches = sum(1 for keyword in child_safety_keywords if keyword in description)
            
            assert matches >= 2, \
                f"Tag {tag_name} should emphasize child safety more"