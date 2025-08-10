"""
Validation utilities for data integrity and COPPA compliance.
Provides comprehensive validation for user inputs and child data.
"""

import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional

try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    # Fallback if email_validator is not installed
    def validate_email(email):
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    class EmailNotValidError(Exception):
        pass


import logging
from src.infrastructure.security.input_validator import ValidationResult

logger = logging.getLogger(__name__)


class ValidationUtils:
    """Data validation utility functions."""

    def __init__(self, strict_mode: bool = False, coppa_compliance: bool = True):
        self.strict_mode = strict_mode
        self.coppa_compliance = coppa_compliance

    def validate_email(self, email: str) -> ValidationResult:
        """Validate email address format."""
        try:
            if callable(validate_email):
                validate_email(email)
                return ValidationResult(True)
            else:
                # Fallback validation
                is_valid = validate_email(email)
                return ValidationResult(
                    is_valid, reason="Invalid email format" if not is_valid else None
                )
        except EmailNotValidError as e:
            logger.warning("Invalid email: %s", e, exc_info=True)
            return ValidationResult(False, reason=str(e))
        except Exception as e:
            logger.error("Email validation error: %s", e)
            return ValidationResult(False, reason="Email validation failed")

    def validate_phone(self, phone: str) -> bool:
        """Validate phone number format."""
        # Remove all non-digit characters
        digits_only = re.sub(r"\D", "", phone)

        # Check if it's a valid length (10-15 digits)
        return 10 <= len(digits_only) <= 15

    def validate_age(self, age: int) -> ValidationResult:
        """Validate age with COPPA compliance."""
        try:
            age_int = int(age)
        except (ValueError, TypeError):
            return ValidationResult(False, reason="Invalid age value")

        is_valid = 0 <= age_int <= 120
        coppa_compliant = 3 <= age_int <= 13 if self.coppa_compliance else True

        if self.coppa_compliance and not coppa_compliant:
            is_valid = False
            reason = f"Age {age_int} is not COPPA compliant (must be 3-13)"
        elif not is_valid:
            reason = f"Age {age_int} is out of valid range (0-120)"
        else:
            reason = None

        return ValidationResult(is_valid, reason=reason)

    def validate_child_name(self, name: str) -> Dict[str, Any]:
        """Validate child name for safety and appropriateness."""
        if not name or not name.strip():
            return {"valid": False, "reason": "Name cannot be empty"}

        name = name.strip()

        # Check length
        if len(name) < 2:
            return {"valid": False, "reason": "Name too short"}

        if len(name) > 50:
            return {"valid": False, "reason": "Name too long"}

        # Check for inappropriate characters
        if re.search(r'[0-9@#$%^&*()_+=\[\]{}|;\':",./<>?`~]', name):
            return {"valid": False, "reason": "Name contains invalid characters"}

        # Check for profanity (simplified)
        if self._contains_profanity(name.lower()):
            return {"valid": False, "reason": "Name contains inappropriate content"}

        return {"valid": True, "sanitized_name": name}


# دالة مستقلة لفحص قوة كلمة المرور
def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength."""
    requirements = {
        "min_length": len(password) >= 8,
        "has_uppercase": bool(re.search(r"[A-Z]", password)),
        "has_lowercase": bool(re.search(r"[a-z]", password)),
        "has_digit": bool(re.search(r"\d", password)),
        "has_special": bool(
            re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?`~]', password)
        ),
    }

    strength_score = sum(requirements.values())
    meets_requirements = all(requirements.values())

    # استخدم دالة feedback من الكلاس إذا كانت موجودة
    def _get_password_feedback(requirements: Dict[str, bool]) -> List[str]:
        feedback = []
        if not requirements["min_length"]:
            feedback.append("Password must be at least 8 characters.")
        if not requirements["has_uppercase"]:
            feedback.append("Add at least one uppercase letter.")
        if not requirements["has_lowercase"]:
            feedback.append("Add at least one lowercase letter.")
        if not requirements["has_digit"]:
            feedback.append("Add at least one digit.")
        if not requirements["has_special"]:
            feedback.append("Add at least one special character.")
        return feedback

    return {
        "strength": strength_score,
        "meets_requirements": meets_requirements,
        "requirements": requirements,
        "feedback": _get_password_feedback(requirements),
    }

    def sanitize_input(self, input_text: str) -> str:
        """Sanitize user input to prevent XSS and injection attacks."""
        if not input_text:
            return ""

        # Remove HTML tags
        clean_text = re.sub(r"<[^>]+>", "", input_text)

        # Remove javascript: protocols
        clean_text = re.sub(r"javascript:", "", clean_text, flags=re.IGNORECASE)

        # Remove on* event handlers
        clean_text = re.sub(r"\bon\w+\s*=", "", clean_text, flags=re.IGNORECASE)

        return clean_text.strip()

    def validate_json_structure(
        self, data: Dict[str, Any], expected_schema: Dict[str, type]
    ) -> Dict[str, Any]:
        """Validate JSON data structure against expected schema."""
        errors = []

        for field, expected_type in expected_schema.items():
            if field not in data:
                errors.append(f"Missing required field: {field}")
                continue

            if not isinstance(data[field], expected_type):
                errors.append(
                    f"Field '{field}' must be of type {expected_type.__name__}"
                )

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_file_upload(
        self, file_info: Dict[str, Any], allowed_types: List[str] = None
    ) -> Dict[str, Any]:
        """Validate file upload for safety and type."""
        if not file_info.get("filename"):
            return {"valid": False, "reason": "No filename provided"}

        filename = file_info["filename"].lower()
        extension = filename.split(".")[-1] if "." in filename else ""
        content_type = file_info.get("content_type", "").lower()
        file_size = file_info.get("size", 0)

        # Check dangerous extensions
        dangerous_extensions = [
            "exe",
            "bat",
            "cmd",
            "scr",
            "pif",
            "vbs",
            "js",
            "jar",
            "com",
        ]
        if extension in dangerous_extensions:
            return {"valid": False, "safe": False, "reason": "Dangerous file type"}

        # Check allowed types
        if allowed_types and content_type not in allowed_types:
            return {"valid": False, "reason": f"File type {content_type} not allowed"}

        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            return {"valid": False, "reason": "File too large"}

        return {"valid": True, "safe": True}

    def _get_age_group(self, age: int) -> str:
        """Get age group classification."""
        if age < 3:
            return "toddler"
        elif age <= 5:
            return "preschool"
        elif age <= 8:
            return "elementary"
        elif age <= 13:
            return "preteen"
        else:
            return "teen_or_adult"

    def _contains_profanity(self, text: str) -> bool:
        """Check if text contains profanity (simplified implementation)."""
        # This is a very basic implementation
        # In production, use a comprehensive profanity filter
        basic_profanity = ["damn", "hell", "crap"]  # Very mild examples
        return any(word in text.lower() for word in basic_profanity)

    def _get_password_feedback(self, requirements: Dict[str, bool]) -> List[str]:
        """Get password improvement feedback."""
        feedback = []

        if not requirements["min_length"]:
            feedback.append("Use at least 8 characters")
        if not requirements["has_uppercase"]:
            feedback.append("Include uppercase letters")
        if not requirements["has_lowercase"]:
            feedback.append("Include lowercase letters")
        if not requirements["has_digit"]:
            feedback.append("Include numbers")
        if not requirements["has_special"]:
            feedback.append("Include special characters")

        return feedback


class DataValidator:
    """Advanced data validation for complex structures."""

    def __init__(self, validation_utils: Optional[ValidationUtils] = None):
        self.validator = validation_utils or ValidationUtils()

    def validate_child_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate complete child profile data."""
        errors = []
        warnings = []

        # Validate required fields
        required_fields = ["name", "birth_date", "parent_id"]
        for field in required_fields:
            if field not in profile_data:
                errors.append(f"Missing required field: {field}")

        # Validate name
        if "name" in profile_data:
            name_result = self.validator.validate_child_name(profile_data["name"])
            if not name_result["valid"]:
                errors.append(f"Invalid name: {name_result['reason']}")

        # Validate age from birth date
        if "birth_date" in profile_data:
            try:
                birth_date = datetime.strptime(
                    profile_data["birth_date"], "%Y-%m-%d"
                ).date()
                age = (date.today() - birth_date).days // 365
                age_result = self.validator.validate_age(age)

                if not age_result["valid"]:
                    errors.append("Invalid age")
                if not age_result["coppa_compliant"]:
                    errors.append("Age not COPPA compliant (must be 3-13)")
            except ValueError:
                errors.append("Invalid birth date format")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_conversation_message(
        self, message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate conversation message data."""
        errors = []

        # Check required fields
        if not message_data.get("content"):
            errors.append("Message content cannot be empty")

        if not message_data.get("child_id"):
            errors.append("Child ID is required")

        # Validate content length
        content = message_data.get("content", "")
        if len(content) > 1000:
            errors.append("Message too long")

        # Sanitize content
        sanitized_content = self.validator.sanitize_input(content)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "sanitized_content": sanitized_content,
        }
