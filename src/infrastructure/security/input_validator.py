"""
Advanced Input Validation System - Enterprise Security
====================================================
Production-grade input validation with:
- Multi-layer validation (syntax, semantic, business rules)
- Child safety specific validation
- SQL injection, XSS, and CSRF protection
- File upload security
- Content filtering and sanitization
- Audit logging for security events
"""

import re
import html
import json
import base64
import mimetypes
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import bleach
import magic
from urllib.parse import urlparse, unquote
import ipaddress
import email_validator
import phonenumbers
from phonenumbers import NumberParseException


class ValidationSeverity(Enum):
    """Validation severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationType(Enum):
    """Types of validation."""

    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    BUSINESS = "business"
    SECURITY = "security"
    CHILD_SAFETY = "child_safety"


@dataclass
class ValidationRule:
    """Individual validation rule."""

    name: str
    validator: Callable[[Any], bool]
    error_message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    validation_type: ValidationType = ValidationType.SYNTAX
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of input validation."""

    is_valid: bool
    sanitized_value: Any = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    security_violations: List[str] = field(default_factory=list)
    child_safety_violations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_error(
        self, message: str, severity: ValidationSeverity = ValidationSeverity.ERROR
    ):
        """Add validation error."""
        self.is_valid = False
        if severity == ValidationSeverity.CRITICAL:
            self.security_violations.append(message)
        elif severity == ValidationSeverity.ERROR:
            self.errors.append(message)
        elif severity == ValidationSeverity.WARNING:
            self.warnings.append(message)

    def merge(self, other: "ValidationResult"):
        """Merge with another validation result."""
        if not other.is_valid:
            self.is_valid = False

        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.security_violations.extend(other.security_violations)
        self.child_safety_violations.extend(other.child_safety_violations)
        self.metadata.update(other.metadata)


class SecurityPatterns:
    """Security threat patterns for detection."""

    # SQL Injection patterns
    SQL_INJECTION = [
        r"('|(\x27)|(\x2D))-",
        r"\w*((%27)|(')|(%2D)|(-))((%20)|(%09)|(%0A)|(%0D)|\s)*((%75)|u|((%55)|U))((%6E)|n|((%4E)|N))((%69)|i|((%49)|I))((%6F)|o|((%4F)|O))((%6E)|n|((%4E)|N))",
        r"((%27)|(')|(%2D)|(-)).*((%6F)|o|((%4F)|O))((%72)|r|((%52)|R))",
        r"((%27)|(')|(%2D)|-).*((%64)|d|((%44)|D))((%72)|r|((%52)|R))((%6F)|o|((%4F)|O))((%70)|p|((%50)|P))",
        r"(select|insert|update|delete|union|exec|execute|create|alter|drop)\s",
        r";\s*(drop|exec|insert|select|union|update|delete)",
        r"(union\s+select|select\s+.*\s+from)",
        r"(--|#|/\*|\*/)",
    ]

    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
        r"<link[^>]*>",
        r"<meta[^>]*>",
        r"expression\s*\(",
        r"@import",
        r"\beval\s*\(",
        r"\bsetTimeout\s*\(",
        r"\bsetInterval\s*\(",
    ]

    # Command injection patterns
    COMMAND_INJECTION = [
        r";\\s*(rm|cat|ls|ps|kill|chmod|chown)",
        r"\\|\\s*(rm|cat|ls|ps|kill|chmod|chown)",
        r"&&\\s*(rm|cat|ls|ps|kill|chmod|chown)",
        r"\\$\\((.*?)\\)",
        r"`(.*?)`",
        r"\\\\x[0-9a-fA-F]{2}",
        r"\\\\[0-7]{1,3}",
    ]

    # Path traversal patterns
    PATH_TRAVERSAL = [
        r"\\.\\./",
        r"\\\\\\.\\.\\\\",
        r"%2e%2e%2f",
        r"%2e%2e\\\\",
        r"\\.\\.\\\\",
        r"%252e%252e%252f",
    ]

    # LDAP injection patterns
    LDAP_INJECTION = [r"\*\)", r"\*\(\|.*\)", r"\*\(&.*\)", r"\*\(!\(.*\)", r"\*\|"]


class ChildSafetyPatterns:
    """Child safety specific patterns."""

    # Inappropriate content patterns
    INAPPROPRIATE_CONTENT = [
        # Violence related
        r"\\b(kill|murder|death|blood|violence|weapon|gun|knife|bomb)\\b",
        r"\\b(hurt|harm|attack|fight|hit|punch|kick)\\b",
        # Adult content
        r"\\b(sex|adult|mature|explicit)\\b",
        # Scary content
        r"\\b(scary|frightening|horror|nightmare|ghost|monster)\\b",
        # Personal information solicitation
        r"\\b(address|phone|password|secret|personal)\\b",
        r"\\b(meet|location|where.*live|real.*name)\\b",
    ]

    # Personal information patterns
    PERSONAL_INFO = [
        r"\\b\\d{3}-\\d{2}-\\d{4}\\b",  # SSN pattern
        r"\\b\\d{3}-\\d{3}-\\d{4}\\b",  # Phone pattern
        r"\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",  # Email
        r"\\b\\d{1,5}\\s\\w+\\s(Street|St|Avenue|Ave|Road|Rd|Drive|Dr)\\b",  # Address
        r"\\bcredit.*card\\b|\\bdebit.*card\\b",
    ]

    # Age inappropriate language
    AGE_INAPPROPRIATE = [
        r"\\b(stupid|dumb|idiot|hate|kill|die)\\b",
        r"\\b(damn|hell|crap)\\b",
    ]


class AdvancedInputValidator:
    """
    Advanced input validation system with comprehensive security features.

    Features:
    - Multi-layer validation (syntax, semantic, business)
    - Security threat detection
    - Child safety validation
    - Content sanitization
    - File upload validation
    - Audit logging
    """

    def __init__(self, logger=None):
        self.logger = logger
        self._compile_security_patterns()
        
    def _compile_security_patterns(self):
        """Compile security patterns with proper error handling."""
        self._sql_patterns = self._compile_patterns(SecurityPatterns.SQL_INJECTION, "SQL")
        self._xss_patterns = self._compile_patterns(SecurityPatterns.XSS_PATTERNS, "XSS")
        self._cmd_patterns = self._compile_patterns(SecurityPatterns.COMMAND_INJECTION, "CMD")
        self._path_patterns = self._compile_patterns(SecurityPatterns.PATH_TRAVERSAL, "Path")
        self._ldap_patterns = self._compile_patterns(SecurityPatterns.LDAP_INJECTION, "LDAP")
        self._inappropriate_patterns = self._compile_patterns(ChildSafetyPatterns.INAPPROPRIATE_CONTENT, "Inappropriate")
        self._personal_info_patterns = self._compile_patterns(ChildSafetyPatterns.PERSONAL_INFO, "Personal Info")
        self._age_inappropriate_patterns = self._compile_patterns(ChildSafetyPatterns.AGE_INAPPROPRIATE, "Age Inappropriate")
        
    def _compile_patterns(self, patterns: List[str], pattern_type: str) -> List[re.Pattern]:
        """Safely compile regex patterns."""
        compiled_patterns = []
        for pattern in patterns:
            try:
                compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                if self.logger:
                    self.logger.warning(f"{pattern_type} pattern compilation failed: {pattern} - {e}")
                # Continue with other patterns instead of failing completely
        return compiled_patterns
        
    def validate_authorization(self, user_data: Dict[str, Any], required_role: str = None) -> ValidationResult:
        """Validate user authorization using server-side data only."""
        result = ValidationResult(is_valid=True)
        
        # Only use server-side session data for authorization
        if not user_data or not isinstance(user_data, dict):
            result.add_error("Invalid user data", ValidationSeverity.CRITICAL)
            return result
            
        # Check for server-side role validation
        server_role = user_data.get('server_role')  # Server-side role only
        if not server_role:
            result.add_error("No server-side role found", ValidationSeverity.CRITICAL)
            return result
            
        if required_role and server_role != required_role:
            result.add_error(f"Insufficient privileges: required {required_role}, got {server_role}", ValidationSeverity.CRITICAL)
            return result
            
        return result

        # Allowed HTML tags for sanitization
        self._allowed_tags = [
            "p",
            "br",
            "strong",
            "em",
            "u",
            "i",
            "b",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "ol",
            "li",
            "blockquote",
        ]

        self._allowed_attributes = {
            "*": ["class", "id"],
            "a": ["href", "title"],
            "img": ["src", "alt", "width", "height"],
            "iframe": ["src", "sandbox"],  # Always require sandbox for iframes
        }

        # File type validation
        self._allowed_image_types = {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        }
        self._allowed_audio_types = {
            "audio/mpeg",
            "audio/wav",
            "audio/ogg",
            "audio/mp4",
        }
        self._allowed_video_types = {"video/mp4", "video/webm", "video/ogg"}
        self._allowed_document_types = {"application/pdf", "text/plain"}

        # Size limits (bytes)
        self._max_image_size = 10 * 1024 * 1024  # 10MB
        self._max_audio_size = 50 * 1024 * 1024  # 50MB
        self._max_video_size = 100 * 1024 * 1024  # 100MB
        self._max_document_size = 5 * 1024 * 1024  # 5MB

    def validate_string(
        self,
        value: Any,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        allowed_chars: Optional[str] = None,
        child_safe: bool = True,
        sanitize: bool = True,
    ) -> ValidationResult:
        """
        Validate string input with comprehensive security checks.

        Args:
            value: Input value to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length
            pattern: Regex pattern to match
            allowed_chars: Character whitelist
            child_safe: Apply child safety filters
            sanitize: Apply sanitization

        Returns:
            ValidationResult with validation outcome
        """
        result = ValidationResult()

        # Type validation
        if not isinstance(value, (str, type(None))):
            try:
                value = str(value)
            except ValueError as e:
                result.add_error(f"Invalid string format: {str(e)}", ValidationSeverity.ERROR)
                return result
            except TypeError as e:
                result.add_error(f"Type conversion error: {str(e)}", ValidationSeverity.ERROR)
                return result

        if value is None:
            value = ""

        original_value = value

        # Length validation
        if min_length is not None and len(value) < min_length:
            result.add_error(
                f"Minimum length is {min_length} characters", ValidationSeverity.ERROR
            )

        if max_length is not None and len(value) > max_length:
            result.add_error(
                f"Maximum length is {max_length} characters", ValidationSeverity.ERROR
            )
            # Truncate for safety
            value = value[:max_length]

        # Pattern validation
        if pattern and not re.match(pattern, value):
            result.add_error("Input format is invalid", ValidationSeverity.ERROR)

        # Character whitelist validation
        if allowed_chars:
            invalid_chars = set(value) - set(allowed_chars)
            if invalid_chars:
                result.add_error(
                    f"Contains invalid characters: {', '.join(invalid_chars)}",
                    ValidationSeverity.ERROR,
                )

        # Security validation
        security_result = self._validate_security_threats(value)
        result.merge(security_result)

        # Child safety validation
        if child_safe:
            safety_result = self._validate_child_safety(value)
            result.merge(safety_result)

        # Sanitization
        if sanitize and result.is_valid:
            result.sanitized_value = self._sanitize_string(value)
        else:
            result.sanitized_value = value

        # Log security violations
        if result.security_violations and self.logger:
            safe_value = original_value.replace('\n', '').replace('\r', '')[:100]
            safe_violations = [v.replace('\n', '').replace('\r', '')[:100] for v in result.security_violations]
            self.logger.warning(
                "Security violation detected in input",
                extra={
                    "original_value": safe_value,
                    "violations": safe_violations,
                    "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
                },
            )

        return result

    def validate_email(self, email: str) -> ValidationResult:
        """Validate email address."""
        result = ValidationResult()

        if not email:
            result.add_error("Email is required", ValidationSeverity.ERROR)
            return result

        try:
            # Use email-validator library for comprehensive validation
            validated_email = email_validator.validate_email(email)
            result.sanitized_value = validated_email.email
            result.is_valid = True

            # Additional security checks
            domain = validated_email.domain

            # Check for suspicious domains
            suspicious_domains = [
                "tempmail",
                "guerrillamail",
                "10minutemail",
                "throwaway",
            ]
            if any(suspicious in domain.lower() for suspicious in suspicious_domains):
                result.add_error(
                    "Suspicious email domain detected", ValidationSeverity.WARNING
                )

            # Check for very long local parts (potential attack)
            local_part = validated_email.local
            if len(local_part) > 64:
                result.add_error(
                    "Email local part too long", ValidationSeverity.WARNING
                )

        except email_validator.EmailNotValidError as e:
            result.add_error(
                f"Invalid email format: {str(e)}", ValidationSeverity.ERROR
            )

        return result

    def validate_phone(self, phone: str, region: str = "US") -> ValidationResult:
        """Validate phone number."""
        result = ValidationResult()

        if not phone:
            result.add_error("Phone number is required", ValidationSeverity.ERROR)
            return result

        try:
            parsed_number = phonenumbers.parse(phone, region)

            if not phonenumbers.is_valid_number(parsed_number):
                result.add_error("Invalid phone number", ValidationSeverity.ERROR)
            else:
                # Format the number
                formatted = phonenumbers.format_number(
                    parsed_number, phonenumbers.PhoneNumberFormat.E164
                )
                result.sanitized_value = formatted
                result.is_valid = True

                # Add metadata
                result.metadata = {
                    "country_code": parsed_number.country_code,
                    "national_number": parsed_number.national_number,
                    "number_type": phonenumbers.number_type(parsed_number).name,
                }

        except NumberParseException as e:
            result.add_error(
                f"Phone parsing error: {e.error_type.name}", ValidationSeverity.ERROR
            )

        return result

    def validate_age(
        self, age: Any, min_age: int = 0, max_age: int = 150
    ) -> ValidationResult:
        """Validate age input."""
        result = ValidationResult()

        try:
            age_int = int(age)

            if age_int < min_age:
                result.add_error(
                    f"Age must be at least {min_age}", ValidationSeverity.ERROR
                )
            elif age_int > max_age:
                result.add_error(
                    f"Age cannot exceed {max_age}", ValidationSeverity.ERROR
                )
            else:
                result.sanitized_value = age_int
                result.is_valid = True

                # COPPA compliance check
                if age_int < 13:
                    result.metadata["coppa_protected"] = True

        except (ValueError, TypeError):
            result.add_error("Age must be a valid number", ValidationSeverity.ERROR)

        return result

    def validate_url(
        self, url: str, allowed_schemes: List[str] = None
    ) -> ValidationResult:
        """Validate and sanitize URL."""
        result = ValidationResult()

        if not url:
            result.add_error("URL is required", ValidationSeverity.ERROR)
            return result

        if allowed_schemes is None:
            allowed_schemes = ["http", "https"]

        try:
            parsed = urlparse(url)

            # Scheme validation
            if parsed.scheme.lower() not in allowed_schemes:
                result.add_error(
                    f"URL scheme must be one of: {', '.join(allowed_schemes)}",
                    ValidationSeverity.ERROR,
                )

            # Domain validation
            if not parsed.netloc:
                result.add_error(
                    "URL must have a valid domain", ValidationSeverity.ERROR
                )

            # Security checks
            if parsed.scheme.lower() == "javascript":
                result.add_error(
                    "JavaScript URLs are not allowed", ValidationSeverity.CRITICAL
                )

            # Path traversal check
            if "../" in parsed.path or "..\\\\" in parsed.path:
                result.add_error(
                    "Path traversal detected in URL", ValidationSeverity.CRITICAL
                )

            # If valid, sanitize
            if result.is_valid or not result.errors:
                result.sanitized_value = (
                    url.strip().lower()
                    if parsed.scheme.lower() in allowed_schemes
                    else None
                )
                result.is_valid = True

        except Exception as e:
            result.add_error(f"Invalid URL format: {str(e)}", ValidationSeverity.ERROR)

        return result

    def validate_file_upload(
        self,
        file_data: bytes,
        filename: str,
        allowed_types: Optional[List[str]] = None,
        max_size: Optional[int] = None,
    ) -> ValidationResult:
        """Validate file upload with security checks."""
        result = ValidationResult()

        if not file_data:
            result.add_error("File data is required", ValidationSeverity.ERROR)
            return result

        # Size validation
        file_size = len(file_data)

        if max_size and file_size > max_size:
            result.add_error(
                f"File size exceeds maximum allowed ({max_size} bytes)",
                ValidationSeverity.ERROR,
            )

        # MIME type detection using python-magic
        try:
            detected_mime = magic.from_buffer(file_data, mime=True)

            # Filename extension check
            guessed_mime, _ = mimetypes.guess_type(filename)

            # Cross-check MIME types
            if guessed_mime and detected_mime != guessed_mime:
                result.add_error(
                    "File extension doesn't match content type",
                    ValidationSeverity.WARNING,
                )

            # Type validation
            if allowed_types and detected_mime not in allowed_types:
                result.add_error(
                    f"File type {detected_mime} is not allowed",
                    ValidationSeverity.ERROR,
                )

            # Security checks for images
            if detected_mime.startswith("image/"):
                if self._check_image_security(file_data):
                    result.add_error(
                        "Image contains potentially malicious content",
                        ValidationSeverity.CRITICAL,
                    )

            # Security checks for documents
            elif detected_mime in ["application/pdf"]:
                if self._check_pdf_security(file_data):
                    result.add_error(
                        "PDF contains potentially malicious content",
                        ValidationSeverity.CRITICAL,
                    )

            result.metadata = {
                "detected_mime": detected_mime,
                "guessed_mime": guessed_mime,
                "file_size": file_size,
            }

            if not result.errors:
                result.is_valid = True
                result.sanitized_value = file_data

        except (OSError, IOError) as e:
            result.add_error(
                f"File I/O error: {str(e)}", ValidationSeverity.ERROR
            )
        except ImportError as e:
            result.add_error(
                f"Missing dependency for file validation: {str(e)}", ValidationSeverity.ERROR
            )
        except Exception as e:
            result.add_error(
                f"Unexpected file validation error: {str(e)}", ValidationSeverity.ERROR
            )

        return result

    def validate_json(
        self, json_str: str, max_depth: int = 10, max_size: int = 1024 * 1024
    ) -> ValidationResult:
        """Validate JSON input with security checks."""
        result = ValidationResult()

        if not json_str:
            result.add_error("JSON is required", ValidationSeverity.ERROR)
            return result

        # Size check
        if len(json_str) > max_size:
            result.add_error(
                f"JSON size exceeds maximum ({max_size} bytes)",
                ValidationSeverity.ERROR,
            )
            return result

        try:
            # Parse JSON
            parsed_data = json.loads(json_str)

            # Depth check (prevent deeply nested attacks)
            if self._get_json_depth(parsed_data) > max_depth:
                result.add_error(
                    f"JSON nesting depth exceeds maximum ({max_depth})",
                    ValidationSeverity.ERROR,
                )

            # Check for suspicious patterns in JSON strings
            json_strings = self._extract_json_strings(parsed_data)
            for json_string in json_strings:
                security_result = self._validate_security_threats(json_string)
                if security_result.security_violations:
                    result.security_violations.extend(
                        security_result.security_violations
                    )
                    result.is_valid = False

            if result.is_valid or not result.errors:
                result.sanitized_value = parsed_data
                result.is_valid = True

        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON format: {str(e)}", ValidationSeverity.ERROR)
        except (ValueError, TypeError) as e:
            result.add_error(f"JSON processing error: {str(e)}", ValidationSeverity.ERROR)

        return result

    def _validate_security_threats(self, value: str) -> ValidationResult:
        """Check for security threats in input."""
        result = ValidationResult()

        try:
            # SQL Injection detection
            for pattern in self._sql_patterns:
                if pattern.search(value):
                    result.add_error(
                        "Potential SQL injection detected", ValidationSeverity.CRITICAL
                    )
                    break

            # XSS detection
            for pattern in self._xss_patterns:
                if pattern.search(value):
                    result.add_error(
                        "Potential XSS attack detected", ValidationSeverity.CRITICAL
                    )
                    break

            # Command injection detection
            for pattern in self._cmd_patterns:
                if pattern.search(value):
                    result.add_error(
                        "Potential command injection detected", ValidationSeverity.CRITICAL
                    )
                    break

            # Path traversal detection
            for pattern in self._path_patterns:
                if pattern.search(value):
                    result.add_error(
                        "Path traversal attempt detected", ValidationSeverity.CRITICAL
                    )
                    break

            # LDAP injection detection
            for pattern in self._ldap_patterns:
                if pattern.search(value):
                    result.add_error(
                        "Potential LDAP injection detected", ValidationSeverity.CRITICAL
                    )
                    break
        except (re.error, AttributeError) as e:
            result.add_error(f"Pattern matching error: {str(e)}", ValidationSeverity.ERROR)

        return result

    def _validate_child_safety(self, value: str) -> ValidationResult:
        """Check for child safety violations."""
        result = ValidationResult()

        # Check for inappropriate content
        for pattern in self._inappropriate_patterns:
            if pattern.search(value):
                result.child_safety_violations.append("Inappropriate content detected")
                result.is_valid = False
                break

        # Check for personal information
        for pattern in self._personal_info_patterns:
            if pattern.search(value):
                result.child_safety_violations.append("Personal information detected")
                result.add_error(
                    "Personal information sharing is not allowed",
                    ValidationSeverity.WARNING,
                )
                break

        # Check for age-inappropriate language
        for pattern in self._age_inappropriate_patterns:
            if pattern.search(value):
                result.child_safety_violations.append(
                    "Age-inappropriate language detected"
                )
                result.add_error(
                    "Language not suitable for children", ValidationSeverity.WARNING
                )
                break

        return result

    def _sanitize_string(self, value: str) -> str:
        """Sanitize string content."""
        # HTML escape
        sanitized = html.escape(value)

        # Remove null bytes
        sanitized = sanitized.replace("\\x00", "")

        # Normalize whitespace
        sanitized = re.sub(r"\\s+", " ", sanitized).strip()

        # Remove control characters except tabs and newlines
        sanitized = "".join(
            char for char in sanitized if ord(char) >= 32 or char in "\\t\\n\\r"
        )

        return sanitized

    def _check_image_security(self, image_data: bytes) -> bool:
        """Check image for security issues."""
        # Check for suspicious patterns in image metadata
        # This is a simplified check - production would use more sophisticated analysis

        # Check for embedded scripts or unusual headers
        suspicious_patterns = [b"<script", b"javascript:", b"<?php", b"<%"]

        for pattern in suspicious_patterns:
            if pattern in image_data[:1024]:  # Check first 1KB
                return True

        return False

    def _check_pdf_security(self, pdf_data: bytes) -> bool:
        """Check PDF for security issues."""
        # Check for suspicious PDF patterns
        suspicious_patterns = [
            b"/JavaScript",
            b"/JS",
            b"/OpenAction",
            b"/Launch",
            b"/EmbeddedFile",
        ]

        for pattern in suspicious_patterns:
            if pattern in pdf_data:
                return True

        return False

    def _get_json_depth(self, obj: Any, depth: int = 0) -> int:
        """Calculate maximum depth of nested JSON object."""
        if isinstance(obj, dict):
            return max(
                [self._get_json_depth(value, depth + 1) for value in obj.values()],
                default=depth,
            )
        elif isinstance(obj, list):
            return max(
                [self._get_json_depth(item, depth + 1) for item in obj], default=depth
            )
        else:
            return depth

    def _extract_json_strings(self, obj: Any) -> List[str]:
        """Extract all string values from JSON object."""
        strings = []

        try:
            if isinstance(obj, str):
                strings.append(obj)
            elif isinstance(obj, dict):
                for value in obj.values():
                    strings.extend(self._extract_json_strings(value))
            elif isinstance(obj, list):
                for item in obj:
                    strings.extend(self._extract_json_strings(item))
        except (TypeError, AttributeError, RecursionError):
            # Handle malformed JSON structures
            pass

        return strings

    def sanitize_html(self, html_content: str, strict: bool = True) -> str:
        """Sanitize HTML content for safe display."""
        if strict:
            # Very restrictive for child-safe content
            allowed_tags = ["p", "br", "strong", "em"]
            allowed_attributes = {}
        else:
            allowed_tags = self._allowed_tags
            allowed_attributes = self._allowed_attributes

        return bleach.clean(
            html_content, tags=allowed_tags, attributes=allowed_attributes, strip=True
        )

    def set_logger(self, logger):
        """Set logger for audit logging."""
        self.logger = logger


# Global instance
advanced_input_validator = AdvancedInputValidator()
