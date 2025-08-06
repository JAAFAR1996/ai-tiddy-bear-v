"""
Tests for Advanced Input Validator - Security Critical
====================================================

Critical security tests for input validation system.
These tests ensure protection against various attack vectors.
"""

import pytest
from unittest.mock import Mock, patch
import json

from src.infrastructure.security.input_validator import (
    AdvancedInputValidator,
    ValidationResult,
    ValidationSeverity,
    ValidationType,
    SecurityPatterns,
    ChildSafetyPatterns
)


class TestAdvancedInputValidator:
    """Test advanced input validation system."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return AdvancedInputValidator()

    def test_validator_initialization(self, validator):
        """Test validator initializes correctly."""
        assert validator is not None
        assert hasattr(validator, '_sql_patterns')
        assert hasattr(validator, '_xss_patterns')
        assert hasattr(validator, '_inappropriate_patterns')

    def test_validate_string_basic(self, validator):
        """Test basic string validation."""
        result = validator.validate_string("Hello World")
        
        assert result.is_valid is True
        assert result.sanitized_value == "Hello World"
        assert len(result.errors) == 0
        assert len(result.security_violations) == 0

    def test_validate_string_length_constraints(self, validator):
        """Test string length validation."""
        # Test minimum length
        result = validator.validate_string("Hi", min_length=5)
        assert result.is_valid is False
        assert "Minimum length is 5" in result.errors[0]
        
        # Test maximum length
        result = validator.validate_string("Very long text here", max_length=10)
        assert result.is_valid is False
        assert "Maximum length is 10" in result.errors[0]
        assert len(result.sanitized_value) == 10  # Should be truncated

    def test_validate_string_pattern_matching(self, validator):
        """Test pattern matching validation."""
        # Valid pattern
        result = validator.validate_string("test123", pattern=r"^[a-z0-9]+$")
        assert result.is_valid is True
        
        # Invalid pattern
        result = validator.validate_string("Test@123", pattern=r"^[a-z0-9]+$")
        assert result.is_valid is False
        assert "Input format is invalid" in result.errors[0]

    def test_validate_string_character_whitelist(self, validator):
        """Test character whitelist validation."""
        result = validator.validate_string(
            "hello123", 
            allowed_chars="abcdefghijklmnopqrstuvwxyz0123456789"
        )
        assert result.is_valid is True
        
        result = validator.validate_string(
            "hello@123", 
            allowed_chars="abcdefghijklmnopqrstuvwxyz0123456789"
        )
        assert result.is_valid is False
        assert "Contains invalid characters" in result.errors[0]

    def test_sql_injection_detection(self, validator):
        """Test SQL injection pattern detection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM users",
            "UNION SELECT * FROM passwords"
        ]
        
        for malicious_input in malicious_inputs:
            result = validator.validate_string(malicious_input)
            assert result.is_valid is False
            assert len(result.security_violations) > 0
            assert any("SQL injection" in violation for violation in result.security_violations)

    def test_xss_attack_detection(self, validator):
        """Test XSS attack pattern detection."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<iframe src='malicious.com'></iframe>",
            "<img onerror='alert(1)' src='x'>",
            "vbscript:msgbox('xss')",
            "<object data='malicious.swf'></object>"
        ]
        
        for malicious_input in malicious_inputs:
            result = validator.validate_string(malicious_input)
            assert result.is_valid is False
            assert len(result.security_violations) > 0
            assert any("XSS attack" in violation for violation in result.security_violations)

    def test_command_injection_detection(self, validator):
        """Test command injection pattern detection."""
        malicious_inputs = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& ls -la",
            "$(whoami)",
            "`id`",
            "\\x41\\x42\\x43"
        ]
        
        for malicious_input in malicious_inputs:
            result = validator.validate_string(malicious_input)
            assert result.is_valid is False
            assert len(result.security_violations) > 0
            assert any("command injection" in violation for violation in result.security_violations)

    def test_path_traversal_detection(self, validator):
        """Test path traversal attack detection."""
        malicious_inputs = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc/passwd"
        ]
        
        for malicious_input in malicious_inputs:
            result = validator.validate_string(malicious_input)
            assert result.is_valid is False
            assert len(result.security_violations) > 0
            assert any("Path traversal" in violation for violation in result.security_violations)

    def test_child_safety_inappropriate_content(self, validator):
        """Test child safety inappropriate content detection."""
        inappropriate_inputs = [
            "I want to kill someone",
            "This is violent content",
            "Let's talk about death and blood",
            "Scary monster will hurt you",
            "Adult content here"
        ]
        
        for inappropriate_input in inappropriate_inputs:
            result = validator.validate_string(inappropriate_input, child_safe=True)
            assert result.is_valid is False
            assert len(result.child_safety_violations) > 0
            assert any("Inappropriate content" in violation for violation in result.child_safety_violations)

    def test_child_safety_personal_info_detection(self, validator):
        """Test personal information detection."""
        personal_info_inputs = [
            "My phone number is 555-123-4567",
            "Email me at test@example.com",
            "I live at 123 Main Street",
            "My SSN is 123-45-6789",
            "Here's my credit card number"
        ]
        
        for personal_input in personal_info_inputs:
            result = validator.validate_string(personal_input, child_safe=True)
            assert result.is_valid is False
            assert len(result.child_safety_violations) > 0
            assert any("Personal information" in violation for violation in result.child_safety_violations)

    def test_child_safety_age_inappropriate_language(self, validator):
        """Test age-inappropriate language detection."""
        inappropriate_language = [
            "You are so stupid",
            "I hate this game",
            "That's really dumb",
            "Go to hell",
            "This is crap"
        ]
        
        for inappropriate_lang in inappropriate_language:
            result = validator.validate_string(inappropriate_lang, child_safe=True)
            assert result.is_valid is False
            assert len(result.child_safety_violations) > 0
            assert any("Age-inappropriate language" in violation for violation in result.child_safety_violations)

    def test_validate_email_valid(self, validator):
        """Test valid email validation."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org"
        ]
        
        for email in valid_emails:
            result = validator.validate_email(email)
            assert result.is_valid is True
            assert "@" in result.sanitized_value

    def test_validate_email_invalid(self, validator):
        """Test invalid email validation."""
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "test@",
            "test..test@example.com",
            ""
        ]
        
        for email in invalid_emails:
            result = validator.validate_email(email)
            assert result.is_valid is False
            assert len(result.errors) > 0

    def test_validate_email_suspicious_domains(self, validator):
        """Test suspicious email domain detection."""
        suspicious_emails = [
            "test@tempmail.com",
            "user@guerrillamail.org",
            "fake@10minutemail.net"
        ]
        
        for email in suspicious_emails:
            result = validator.validate_email(email)
            # Should still be valid but with warning
            assert len(result.warnings) > 0
            assert any("Suspicious email domain" in warning for warning in result.warnings)

    def test_validate_age_valid(self, validator):
        """Test valid age validation."""
        result = validator.validate_age(8)
        assert result.is_valid is True
        assert result.sanitized_value == 8
        assert result.metadata.get("coppa_protected") is True  # Under 13

        result = validator.validate_age(15)
        assert result.is_valid is True
        assert result.sanitized_value == 15
        assert "coppa_protected" not in result.metadata

    def test_validate_age_invalid(self, validator):
        """Test invalid age validation."""
        invalid_ages = [-1, 200, "not_a_number", None]
        
        for age in invalid_ages:
            result = validator.validate_age(age)
            assert result.is_valid is False
            assert len(result.errors) > 0

    def test_validate_url_valid(self, validator):
        """Test valid URL validation."""
        valid_urls = [
            "https://example.com",
            "http://subdomain.example.org/path",
            "https://example.com/path?query=value"
        ]
        
        for url in valid_urls:
            result = validator.validate_url(url)
            assert result.is_valid is True
            assert result.sanitized_value is not None

    def test_validate_url_invalid_scheme(self, validator):
        """Test invalid URL scheme detection."""
        invalid_urls = [
            "javascript:alert('xss')",
            "ftp://example.com",
            "file:///etc/passwd"
        ]
        
        for url in invalid_urls:
            result = validator.validate_url(url)
            assert result.is_valid is False
            if "javascript:" in url:
                assert len(result.security_violations) > 0

    def test_validate_url_path_traversal(self, validator):
        """Test URL path traversal detection."""
        malicious_urls = [
            "https://example.com/../../../etc/passwd",
            "http://example.com/..\\..\\windows\\system32"
        ]
        
        for url in malicious_urls:
            result = validator.validate_url(url)
            assert result.is_valid is False
            assert len(result.security_violations) > 0

    def test_validate_json_valid(self, validator):
        """Test valid JSON validation."""
        valid_json = '{"name": "test", "age": 25, "active": true}'
        result = validator.validate_json(valid_json)
        
        assert result.is_valid is True
        assert isinstance(result.sanitized_value, dict)
        assert result.sanitized_value["name"] == "test"

    def test_validate_json_invalid_format(self, validator):
        """Test invalid JSON format detection."""
        invalid_json = '{"name": "test", "age": 25, "active": true'  # Missing closing brace
        result = validator.validate_json(invalid_json)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Invalid JSON format" in result.errors[0]

    def test_validate_json_too_deep(self, validator):
        """Test JSON depth limit validation."""
        # Create deeply nested JSON
        deep_json = "{" * 15 + '"key": "value"' + "}" * 15
        result = validator.validate_json(deep_json, max_depth=10)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "nesting depth exceeds maximum" in result.errors[0]

    def test_validate_json_with_malicious_content(self, validator):
        """Test JSON with malicious string content."""
        malicious_json = '{"script": "<script>alert(\\"xss\\")</script>", "sql": "\\"; DROP TABLE users; --"}'
        result = validator.validate_json(malicious_json)
        
        assert result.is_valid is False
        assert len(result.security_violations) > 0

    def test_string_sanitization(self, validator):
        """Test string sanitization functionality."""
        dirty_input = "<script>alert('xss')</script>Hello\x00World\t\n  "
        result = validator.validate_string(dirty_input, sanitize=True)
        
        # Should be sanitized
        assert "<script>" not in result.sanitized_value
        assert "\x00" not in result.sanitized_value
        assert result.sanitized_value.strip() != ""

    def test_html_sanitization(self, validator):
        """Test HTML sanitization."""
        malicious_html = '<script>alert("xss")</script><p>Safe content</p><img onerror="alert(1)" src="x">'
        
        # Strict sanitization
        sanitized_strict = validator.sanitize_html(malicious_html, strict=True)
        assert "<script>" not in sanitized_strict
        assert "onerror" not in sanitized_strict
        assert "<p>Safe content</p>" in sanitized_strict

        # Less strict sanitization
        sanitized_normal = validator.sanitize_html(malicious_html, strict=False)
        assert "<script>" not in sanitized_normal
        assert "onerror" not in sanitized_normal

    def test_validation_result_merge(self):
        """Test validation result merging."""
        result1 = ValidationResult()
        result1.add_error("Error 1")
        result1.warnings.append("Warning 1")
        
        result2 = ValidationResult()
        result2.add_error("Error 2")
        result2.security_violations.append("Security violation")
        
        result1.merge(result2)
        
        assert len(result1.errors) == 2
        assert len(result1.warnings) == 1
        assert len(result1.security_violations) == 1
        assert result1.is_valid is False

    def test_logger_integration(self, validator):
        """Test logger integration for security violations."""
        mock_logger = Mock(spec=True)
        validator.set_logger(mock_logger)
        
        # Test with malicious input
        malicious_input = "'; DROP TABLE users; --"
        result = validator.validate_string(malicious_input)
        
        # Should log security violation
        assert mock_logger.warning.called
        call_args = mock_logger.warning.call_args
        assert "Security violation detected" in call_args[0][0]

    @pytest.mark.parametrize("file_type,expected_valid", [
        ("image/jpeg", True),
        ("image/png", True),
        ("application/pdf", True),
        ("text/plain", True),
        ("application/x-executable", False),
        ("text/html", False)
    ])
    def test_file_type_validation(self, validator, file_type, expected_valid):
        """Test file type validation."""
        # Mock file data
        file_data = b"fake file content"
        filename = f"test.{file_type.split('/')[-1]}"
        
        with patch('magic.from_buffer', return_value=file_type):
            with patch('mimetypes.guess_type', return_value=(file_type, None)):
                result = validator.validate_file_upload(
                    file_data, 
                    filename, 
                    allowed_types=["image/jpeg", "image/png", "application/pdf", "text/plain"]
                )
                
                assert result.is_valid == expected_valid

    def test_type_conversion_handling(self, validator):
        """Test handling of different input types."""
        # Test integer conversion to string
        result = validator.validate_string(123)
        assert result.is_valid is True
        assert result.sanitized_value == "123"
        
        # Test None handling
        result = validator.validate_string(None)
        assert result.is_valid is True
        assert result.sanitized_value == ""

    def test_edge_cases(self, validator):
        """Test edge cases and boundary conditions."""
        # Empty string
        result = validator.validate_string("")
        assert result.is_valid is True
        
        # Very long string
        long_string = "a" * 10000
        result = validator.validate_string(long_string, max_length=1000)
        assert result.is_valid is False
        assert len(result.sanitized_value) == 1000
        
        # Unicode characters
        unicode_string = "Hello 世界 🌍"
        result = validator.validate_string(unicode_string)
        assert result.is_valid is True