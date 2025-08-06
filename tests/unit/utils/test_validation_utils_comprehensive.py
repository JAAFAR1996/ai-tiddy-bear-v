"""
Comprehensive unit tests for validation_utils module.
Production-grade validation testing for COPPA compliance and data integrity.
"""

import pytest
from datetime import datetime, date
from unittest.mock import patch, Mock
import logging

from src.utils.validation_utils import ValidationUtils, DataValidator
from email_validator import validate_email as email_validate, EmailNotValidError


class TestValidationUtils:
    """Test ValidationUtils class functionality."""

    @pytest.fixture
    def validation_utils(self):
        """Create ValidationUtils instance for testing."""
        return ValidationUtils()

    @pytest.fixture
    def strict_validation_utils(self):
        """Create ValidationUtils with strict mode enabled."""
        return ValidationUtils(strict_mode=True, coppa_compliance=True)

    @pytest.fixture
    def non_coppa_validation_utils(self):
        """Create ValidationUtils without COPPA compliance."""
        return ValidationUtils(strict_mode=False, coppa_compliance=False)

    def test_init_default_parameters(self):
        """Test ValidationUtils initialization with default parameters."""
        utils = ValidationUtils()
        assert utils.strict_mode is False
        assert utils.coppa_compliance is True

    def test_init_custom_parameters(self):
        """Test ValidationUtils initialization with custom parameters."""
        utils = ValidationUtils(strict_mode=True, coppa_compliance=False)
        assert utils.strict_mode is True
        assert utils.coppa_compliance is False

    def test_validate_email_valid_with_library(self, validation_utils):
        """Test email validation with valid email using library."""
        valid_emails = [
            "user@example.com",
            "test.user@domain.co.uk",
            "name+tag@company.org",
            "firstname.lastname@subdomain.example.com"
        ]
        
        for email in valid_emails:
            result = validation_utils.validate_email(email)
            assert result.is_valid is True

    def test_validate_email_fallback_implementation(self, validation_utils):
        """Test email validation fallback implementation."""
        # Test fallback regex validation
        with patch('src.utils.validation_utils.validate_email', spec=email_validate, side_effect=ImportError()):
            result = validation_utils.validate_email("test@example.com")
            assert result.is_valid is True
            
            result = validation_utils.validate_email("invalid-email")
            assert result.is_valid is False

    def test_validate_email_error_handling(self, validation_utils):
        """Test email validation error handling."""
        
        with patch('src.utils.validation_utils.validate_email', spec=email_validate) as mock_validate:
            mock_validate.side_effect = EmailNotValidError("Invalid email format")
            
            result = validation_utils.validate_email("invalid@email")
            assert result.is_valid is False
            assert "Invalid email format" in result.reason

    def test_validate_phone_valid(self, validation_utils):
        """Test phone validation with valid phone numbers."""
        valid_phones = [
            "1234567890",           # 10 digits
            "+1-234-567-8900",      # With formatting
            "(123) 456-7890",       # US format
            "+44 20 7946 0958",     # International
            "123456789012345"       # 15 digits
        ]
        
        for phone in valid_phones:
            assert validation_utils.validate_phone(phone) is True

    def test_validate_phone_invalid(self, validation_utils):
        """Test phone validation with invalid phone numbers."""
        invalid_phones = [
            "123456789",        # Too short (9 digits)
            "1234567890123456", # Too long (16 digits)
            "abcdefghij",       # Letters
            "",                 # Empty
            "12345"             # Way too short
        ]
        
        for phone in invalid_phones:
            assert validation_utils.validate_phone(phone) is False

    def test_validate_age_coppa_compliant(self, validation_utils):
        """Test age validation with COPPA compliance enabled."""
        test_cases = [
            (3, True),   # Min COPPA age
            (8, True),   # Middle COPPA age  
            (13, True),  # Max COPPA age
            (2, False),  # Too young
            (14, False), # Too old for COPPA
            (0, False),  # Newborn
            (15, False), # Teen
            (-1, False), # Invalid negative
            ("8", True), # String that converts to valid age
            ("invalid", False) # Invalid string
        ]
        
        for age, expected_valid in test_cases:
            result = validation_utils.validate_age(age)
            assert result.is_valid == expected_valid

    def test_validate_age_without_coppa(self, non_coppa_validation_utils):
        """Test age validation without COPPA compliance."""
        test_cases = [
            (0, True),    # Valid without COPPA
            (2, True),    # Valid without COPPA
            (14, True),   # Valid without COPPA
            (120, True),  # Max valid age
            (-1, False),  # Invalid negative
            (121, False)  # Invalid too old
        ]
        
        for age, expected_valid in test_cases:
            result = non_coppa_validation_utils.validate_age(age)
            assert result.is_valid == expected_valid

    def test_validate_child_name_valid(self, validation_utils):
        """Test child name validation with valid names."""
        valid_names = [
            "John",
            "Mary Jane",
            "Jean-Pierre",
            "María"
        ]
        
        for name in valid_names:
            result = validation_utils.validate_child_name(name)
            assert result["valid"] is True
            assert "sanitized_name" in result

    def test_validate_child_name_invalid(self, validation_utils):
        """Test child name validation with invalid names."""
        test_cases = [
            ("", "Name cannot be empty"),
            ("   ", "Name cannot be empty"),
            ("A", "Name too short"),
            ("A" * 51, "Name too long"),
            ("John123", "Name contains invalid characters"),
            ("User@Name", "Name contains invalid characters"),
            ("Name#1", "Name contains invalid characters"),
            ("damn", "Name contains inappropriate content")
        ]
        
        for name, expected_reason in test_cases:
            result = validation_utils.validate_child_name(name)
            assert result["valid"] is False
            assert result["reason"] == expected_reason

    def test_validate_password_strength_strong(self, validation_utils):
        """Test password strength validation with strong passwords."""
        strong_passwords = [
            "StrongP@ss123",
            "MySecure#Pass99",
            "Complex!ty2023",
            "P@ssw0rd!Strong"
        ]
        
        for password in strong_passwords:
            result = validation_utils.validate_password_strength(password)
            assert result["meets_requirements"] is True
            assert result["strength"] == 5
            assert all(result["requirements"].values())
            assert len(result["feedback"]) == 0

    def test_validate_password_strength_weak(self, validation_utils):
        """Test password strength validation with weak passwords."""
        test_cases = [
            ("short", 4),    # Missing length, uppercase, digits, special
            ("password", 3), # Missing uppercase, digits, special
            ("PASSWORD", 3), # Missing lowercase, digits, special
            ("Pass1!", 1),   # Only missing length
            ("pass@word", 2) # Missing uppercase, digits
        ]
        
        for password, expected_missing in test_cases:
            result = validation_utils.validate_password_strength(password)
            assert result["meets_requirements"] is False
            assert len(result["feedback"]) == expected_missing

    def test_sanitize_input_html_removal(self, validation_utils):
        """Test input sanitization removes HTML."""
        test_cases = [
            ("<script>alert('xss')</script>", "alert('xss')"),
            ("<p>Hello <b>World</b></p>", "Hello World"),
            ("Normal text", "Normal text"),
            ("<img src=x onerror=alert(1)>", ""),
            ("<a href='javascript:alert(1)'>Click</a>", "Click")
        ]
        
        for input_text, expected in test_cases:
            result = validation_utils.sanitize_input(input_text)
            assert result == expected

    def test_sanitize_input_javascript_removal(self, validation_utils):
        """Test input sanitization removes JavaScript."""
        dangerous_inputs = [
            "javascript:alert(1)",
            "JAVASCRIPT:void(0)",
            "onclick=alert(1)",
            "onmouseover=doEvil()",
            "onerror=hack()"
        ]
        
        for dangerous in dangerous_inputs:
            result = validation_utils.sanitize_input(dangerous)
            assert "javascript:" not in result.lower()
            # Check that event handlers are removed
            if "on" in dangerous and "=" in dangerous:
                assert "on" not in result or "=" not in result

    def test_sanitize_input_edge_cases(self, validation_utils):
        """Test input sanitization edge cases."""
        assert validation_utils.sanitize_input("") == ""
        assert validation_utils.sanitize_input(None) == ""
        assert validation_utils.sanitize_input("   spaces   ") == "spaces"

    def test_validate_json_structure_valid(self, validation_utils):
        """Test JSON structure validation with valid data."""
        schema = {
            "name": str,
            "age": int,
            "active": bool,
            "scores": list
        }
        
        valid_data = {
            "name": "Test User",
            "age": 25,
            "active": True,
            "scores": [90, 85, 88]
        }
        
        result = validation_utils.validate_json_structure(valid_data, schema)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_json_structure_invalid(self, validation_utils):
        """Test JSON structure validation with invalid data."""
        schema = {
            "name": str,
            "age": int,
            "email": str
        }
        
        invalid_data = {
            "name": 123,  # Wrong type
            "age": "25"   # Wrong type
            # Missing email
        }
        
        result = validation_utils.validate_json_structure(invalid_data, schema)
        assert result["valid"] is False
        assert len(result["errors"]) == 3
        assert "Missing required field: email" in result["errors"]
        assert "Field 'name' must be of type str" in result["errors"]
        assert "Field 'age' must be of type int" in result["errors"]

    def test_validate_file_upload_valid(self, validation_utils):
        """Test file upload validation with valid files."""
        valid_files = [
            {
                "filename": "document.pdf",
                "content_type": "application/pdf",
                "size": 1024 * 1024  # 1MB
            },
            {
                "filename": "image.jpg",
                "content_type": "image/jpeg",
                "size": 500 * 1024  # 500KB
            }
        ]
        
        for file_info in valid_files:
            result = validation_utils.validate_file_upload(file_info, ["application/pdf", "image/jpeg"])
            assert result["valid"] is True
            assert result["safe"] is True

    def test_validate_file_upload_dangerous(self, validation_utils):
        """Test file upload validation with dangerous files."""
        dangerous_files = [
            {"filename": "virus.exe", "size": 1024},
            {"filename": "script.bat", "size": 1024},
            {"filename": "hack.vbs", "size": 1024},
            {"filename": "malware.jar", "size": 1024}
        ]
        
        for file_info in dangerous_files:
            result = validation_utils.validate_file_upload(file_info)
            assert result["valid"] is False
            assert result["safe"] is False
            assert result["reason"] == "Dangerous file type"

    def test_validate_file_upload_size_limit(self, validation_utils):
        """Test file upload validation with size limits."""
        large_file = {
            "filename": "large.pdf",
            "content_type": "application/pdf",
            "size": 11 * 1024 * 1024  # 11MB
        }
        
        result = validation_utils.validate_file_upload(large_file)
        assert result["valid"] is False
        assert result["reason"] == "File too large"

    def test_validate_file_upload_edge_cases(self, validation_utils):
        """Test file upload validation edge cases."""
        # No filename
        result = validation_utils.validate_file_upload({})
        assert result["valid"] is False
        assert result["reason"] == "No filename provided"
        
        # No extension
        result = validation_utils.validate_file_upload({"filename": "noextension", "size": 1024})
        assert result["valid"] is True


class TestDataValidator:
    """Test DataValidator class functionality."""

    @pytest.fixture
    def data_validator(self):
        """Create DataValidator instance for testing."""
        return DataValidator()

    @pytest.fixture
    def custom_data_validator(self):
        """Create DataValidator with custom ValidationUtils."""
        custom_utils = ValidationUtils(strict_mode=True)
        return DataValidator(custom_utils)

    def test_init_default(self):
        """Test DataValidator initialization with defaults."""
        validator = DataValidator()
        assert validator.validator is not None
        assert isinstance(validator.validator, ValidationUtils)

    def test_init_with_custom_validator(self):
        """Test DataValidator initialization with custom validator."""
        custom_utils = ValidationUtils(strict_mode=True)
        validator = DataValidator(custom_utils)
        assert validator.validator == custom_utils

    def test_validate_child_profile_valid(self, data_validator):
        """Test child profile validation with valid data."""
        valid_profile = {
            "name": "Alice Smith",
            "birth_date": "2015-06-15",
            "parent_id": "parent_123"
        }
        
        result = data_validator.validate_child_profile(valid_profile)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_child_profile_missing_fields(self, data_validator):
        """Test child profile validation with missing fields."""
        incomplete_profile = {
            "name": "Bob"
            # Missing birth_date and parent_id
        }
        
        result = data_validator.validate_child_profile(incomplete_profile)
        assert result["valid"] is False
        assert "Missing required field: birth_date" in result["errors"]
        assert "Missing required field: parent_id" in result["errors"]

    def test_validate_child_profile_invalid_name(self, data_validator):
        """Test child profile validation with invalid name."""
        profile = {
            "name": "A",  # Too short
            "birth_date": "2015-06-15",
            "parent_id": "parent_123"
        }
        
        result = data_validator.validate_child_profile(profile)
        assert result["valid"] is False
        assert any("Invalid name" in error for error in result["errors"])

    @patch('src.utils.validation_utils.date', spec=date)
    def test_validate_child_profile_coppa_age(self, mock_date, data_validator):
        """Test child profile validation with COPPA age check."""
        mock_date.today.return_value = date(2023, 6, 15)
        
        # Too young for COPPA
        profile = {
            "name": "Baby User",
            "birth_date": "2022-01-01",  # Age 1
            "parent_id": "parent_123"
        }
        
        result = data_validator.validate_child_profile(profile)
        assert result["valid"] is False
        # Check for age validation errors
        assert any("Invalid age" in error or "not COPPA compliant" in error for error in result["errors"])

    def test_validate_child_profile_invalid_date_format(self, data_validator):
        """Test child profile validation with invalid date format."""
        profile = {
            "name": "Charlie",
            "birth_date": "15/06/2015",  # Wrong format
            "parent_id": "parent_123"
        }
        
        result = data_validator.validate_child_profile(profile)
        assert result["valid"] is False
        assert any("Invalid birth date format" in error for error in result["errors"])

    def test_validate_conversation_message_valid(self, data_validator):
        """Test conversation message validation with valid data."""
        valid_message = {
            "content": "Hello, how are you today?",
            "child_id": "child_123"
        }
        
        result = data_validator.validate_conversation_message(valid_message)
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["sanitized_content"] == "Hello, how are you today?"

    def test_validate_conversation_message_empty(self, data_validator):
        """Test conversation message validation with empty content."""
        empty_message = {
            "content": "",
            "child_id": "child_123"
        }
        
        result = data_validator.validate_conversation_message(empty_message)
        assert result["valid"] is False
        assert "Message content cannot be empty" in result["errors"]

    def test_validate_conversation_message_missing_child_id(self, data_validator):
        """Test conversation message validation without child ID."""
        message = {
            "content": "Test message"
        }
        
        result = data_validator.validate_conversation_message(message)
        assert result["valid"] is False
        assert "Child ID is required" in result["errors"]

    def test_validate_conversation_message_too_long(self, data_validator):
        """Test conversation message validation with too long content."""
        long_message = {
            "content": "A" * 1001,  # Over 1000 character limit
            "child_id": "child_123"
        }
        
        result = data_validator.validate_conversation_message(long_message)
        assert result["valid"] is False
        assert "Message too long" in result["errors"]

    def test_validate_conversation_message_sanitization(self, data_validator):
        """Test conversation message content sanitization."""
        dangerous_message = {
            "content": "<script>alert('xss')</script>Hello",
            "child_id": "child_123"
        }
        
        result = data_validator.validate_conversation_message(dangerous_message)
        assert result["valid"] is True
        assert result["sanitized_content"] == "alert('xss')Hello"


class TestValidationUtilsEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def validation_utils(self):
        return ValidationUtils()

    def test_contains_profanity_case_insensitive(self, validation_utils):
        """Test profanity detection is case insensitive."""
        test_cases = [
            "HELL",
            "Hell", 
            "hElL",
            "damn",
            "DAMN", 
            "Crap"
        ]
        
        for text in test_cases:
            # Using private method for testing
            assert validation_utils._contains_profanity(text) is True

    def test_get_age_group_boundaries(self, validation_utils):
        """Test age group classification at boundaries."""
        # Using private method for testing
        assert validation_utils._get_age_group(2) == "toddler"
        assert validation_utils._get_age_group(3) == "preschool"
        assert validation_utils._get_age_group(5) == "preschool"
        assert validation_utils._get_age_group(6) == "elementary"
        assert validation_utils._get_age_group(8) == "elementary"
        assert validation_utils._get_age_group(9) == "preteen"
        assert validation_utils._get_age_group(13) == "preteen"
        assert validation_utils._get_age_group(14) == "teen_or_adult"

    @patch('src.utils.validation_utils.logger', spec=logging.Logger)
    def test_email_validation_logging(self, mock_logger, validation_utils):
        """Test that email validation errors are logged."""
        
        with patch('src.utils.validation_utils.validate_email', spec=email_validate) as mock_validate:
            mock_validate.side_effect = EmailNotValidError("Test error")
            
            result = validation_utils.validate_email("invalid@")
            
            assert result.is_valid is False
            mock_logger.warning.assert_called_once()

    def test_password_feedback_generation(self, validation_utils):
        """Test password feedback generation for different scenarios."""
        test_cases = [
            ("short", ["Use at least 8 characters", "Include uppercase letters", "Include numbers", "Include special characters"]),
            ("shortPASS", ["Use at least 8 characters", "Include numbers", "Include special characters"]),
            ("longpassword", ["Include uppercase letters", "Include numbers", "Include special characters"]),
            ("LONGPASSWORD", ["Include lowercase letters", "Include numbers", "Include special characters"]),
            ("LongPassword", ["Include numbers", "Include special characters"]),
            ("LongPassword123", ["Include special characters"]),
        ]
        
        for password, expected_feedback in test_cases:
            result = validation_utils.validate_password_strength(password)
            assert set(result["feedback"]) == set(expected_feedback)


class TestValidationIntegration:
    """Integration tests for validation workflows."""

    def test_complete_user_registration_validation(self):
        """Test complete user registration validation workflow."""
        validator = ValidationUtils()
        
        # Simulate registration data
        registration_data = {
            "email": "parent@example.com",
            "password": "SecureP@ss123",
            "phone": "+1-234-567-8900",
            "child_name": "Emma Johnson",
            "child_age": 8
        }
        
        # Validate email (using fallback implementation)
        email_result = validator.validate_email(registration_data["email"])
        assert email_result.is_valid is True
        
        # Validate password
        password_result = validator.validate_password_strength(registration_data["password"])
        assert password_result["meets_requirements"] is True
        
        # Validate phone
        assert validator.validate_phone(registration_data["phone"]) is True
        
        # Validate child name
        name_result = validator.validate_child_name(registration_data["child_name"])
        assert name_result["valid"] is True
        
        # Validate child age
        age_result = validator.validate_age(registration_data["child_age"])
        assert age_result.is_valid is True

    def test_message_safety_validation_workflow(self):
        """Test message safety validation workflow."""
        validator = ValidationUtils()
        data_validator = DataValidator(validator)
        
        # Simulate various message scenarios
        test_messages = [
            {
                "content": "Hi there! How are you today?",
                "child_id": "child_123",
                "expected_valid": True
            },
            {
                "content": "<script>alert('hack')</script>",
                "child_id": "child_456",
                "expected_valid": True,  # Valid after sanitization
                "expected_sanitized": "alert('hack')"
            },
            {
                "content": "",
                "child_id": "child_789",
                "expected_valid": False
            }
        ]
        
        for message_data in test_messages:
            result = data_validator.validate_conversation_message({
                "content": message_data["content"],
                "child_id": message_data["child_id"]
            })
            
            assert result["valid"] == message_data["expected_valid"]
            
            if "expected_sanitized" in message_data:
                assert result["sanitized_content"] == message_data["expected_sanitized"]

    def test_file_upload_security_workflow(self):
        """Test file upload security validation workflow."""
        validator = ValidationUtils()
        
        # Test various file upload scenarios
        test_files = [
            # Safe educational content
            {
                "filename": "math_worksheet.pdf",
                "content_type": "application/pdf",
                "size": 500 * 1024,  # 500KB
                "allowed_types": ["application/pdf", "image/jpeg", "image/png"],
                "expected_valid": True,
                "expected_safe": True
            },
            # Image for profile
            {
                "filename": "profile_pic.jpg",
                "content_type": "image/jpeg",
                "size": 2 * 1024 * 1024,  # 2MB
                "allowed_types": ["image/jpeg", "image/png"],
                "expected_valid": True,
                "expected_safe": True
            },
            # Dangerous executable
            {
                "filename": "game.exe",
                "content_type": "application/x-executable",
                "size": 100 * 1024,
                "allowed_types": None,
                "expected_valid": False,
                "expected_safe": False
            },
            # Too large file
            {
                "filename": "video.mp4",
                "content_type": "video/mp4",
                "size": 15 * 1024 * 1024,  # 15MB
                "allowed_types": ["video/mp4"],
                "expected_valid": False,
                "expected_safe": None
            }
        ]
        
        for file_data in test_files:
            result = validator.validate_file_upload(
                {
                    "filename": file_data["filename"],
                    "content_type": file_data["content_type"],
                    "size": file_data["size"]
                },
                file_data["allowed_types"]
            )
            
            assert result["valid"] == file_data["expected_valid"]
            
            if file_data["expected_safe"] is not None:
                assert result.get("safe") == file_data["expected_safe"]

    def test_coppa_compliance_validation_workflow(self):
        """Test COPPA compliance validation across different scenarios."""
        coppa_validator = ValidationUtils(coppa_compliance=True)
        non_coppa_validator = ValidationUtils(coppa_compliance=False)
        
        test_ages = [2, 3, 8, 13, 14, 16]
        
        for age in test_ages:
            coppa_result = coppa_validator.validate_age(age)
            non_coppa_result = non_coppa_validator.validate_age(age)
            
            # COPPA compliant validator should only accept ages 3-13
            if 3 <= age <= 13:
                assert coppa_result.is_valid is True
            else:
                assert coppa_result.is_valid is False
            
            # Non-COPPA validator should accept all reasonable ages
            if 0 <= age <= 120:
                assert non_coppa_result.is_valid is True
            else:
                assert non_coppa_result.is_valid is False


class TestValidationPerformance:
    """Test validation performance and edge cases."""

    @pytest.fixture
    def validation_utils(self):
        return ValidationUtils()

    def test_large_input_sanitization(self, validation_utils):
        """Test sanitization performance with large inputs."""
        large_input = "<script>alert('xss')</script>" * 1000
        result = validation_utils.sanitize_input(large_input)
        
        # Should not contain script tags
        assert "<script>" not in result
        assert "alert('xss')" in result  # Content should remain

    def test_complex_password_validation(self, validation_utils):
        """Test password validation with complex scenarios."""
        complex_passwords = [
            "P@ssw0rd!2023_VeryLongPasswordWithManyCharacters",
            "简单密码123!",  # Unicode password
            "🔐Secure🔑Pass123!",  # Emoji password
            "P" + "a" * 100 + "1!",  # Very long password
        ]
        
        for password in complex_passwords:
            result = validation_utils.validate_password_strength(password)
            # Should handle all complex cases without errors
            assert isinstance(result, dict)
            assert "strength" in result
            assert "meets_requirements" in result

    def test_bulk_validation_consistency(self, validation_utils):
        """Test validation consistency across bulk operations."""
        test_emails = ["test@example.com"] * 100
        
        results = []
        for email in test_emails:
            result = validation_utils.validate_email(email)
            results.append(result.is_valid)
        
        # All results should be consistent
        assert all(results) or not any(results)  # All True or all False