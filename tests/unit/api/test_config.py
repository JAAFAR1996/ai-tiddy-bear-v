"""
Tests for API configuration module - real configuration validation
"""
import pytest
import os
from unittest.mock import Mock, patch

from src.api.config import (
    ALLOWED_INTERESTS,
    SUPPORTED_LANGUAGES,
    INAPPROPRIATE_WORDS,
    PHONE_PATTERN,
    PASSWORD_PATTERN,
    XSS_PATTERNS,
    CONTENT_FILTER_LEVELS,
    MIN_CHILD_AGE,
    MAX_CHILD_AGE,
    COPPA_AGE_LIMIT,
    DEFAULT_SAFETY_THRESHOLD,
    get_rate_limit_config,
    get_safety_config
)


class TestConstants:
    def test_allowed_interests_completeness(self):
        """Test allowed interests cover major child interests."""
        expected_categories = {
            'animals', 'dinosaurs', 'space', 'science', 'art', 'music',
            'sports', 'books', 'nature', 'cooking', 'games', 'stories'
        }
        
        assert expected_categories.issubset(ALLOWED_INTERESTS)
        assert len(ALLOWED_INTERESTS) >= 20  # Should have good variety
        
        # All interests should be lowercase strings
        for interest in ALLOWED_INTERESTS:
            assert isinstance(interest, str)
            assert interest.islower()
            assert len(interest) > 2  # Meaningful names

    def test_supported_languages_coverage(self):
        """Test supported languages include major world languages."""
        expected_languages = ['en', 'es', 'fr', 'de', 'ar', 'zh']
        
        for lang in expected_languages:
            assert lang in SUPPORTED_LANGUAGES
        
        # All should be 2-character ISO codes
        for lang in SUPPORTED_LANGUAGES:
            assert isinstance(lang, str)
            assert len(lang) == 2
            assert lang.islower()

    def test_inappropriate_words_coverage(self):
        """Test inappropriate words cover key safety categories."""
        # Personal information
        personal_info = ['password', 'address', 'phone', 'email']
        for word in personal_info:
            assert word in INAPPROPRIATE_WORDS
        
        # Location information
        location_info = ['street', 'home address', 'school name']
        for word in location_info:
            assert word in INAPPROPRIATE_WORDS
        
        # All should be lowercase
        for word in INAPPROPRIATE_WORDS:
            assert isinstance(word, str)
            assert word.islower()

    def test_phone_pattern_validation(self):
        """Test phone pattern validates international formats."""
        import re
        
        valid_phones = [
            '+1234567890',
            '+44123456789',
            '+861234567890',
            '1234567890'
        ]
        
        invalid_phones = [
            '123',  # Too short
            'abc123',  # Contains letters
            '+',  # Just plus
            ''  # Empty
        ]
        
        for phone in valid_phones:
            assert re.match(PHONE_PATTERN, phone), f"Should accept {phone}"
        
        for phone in invalid_phones:
            assert not re.match(PHONE_PATTERN, phone), f"Should reject {phone}"

    def test_password_pattern_validation(self):
        """Test password pattern enforces security requirements."""
        import re
        
        valid_passwords = [
            'SecureP@ssw0rd!',
            'MyStr0ng#Pass',
            'Ch1ld$afe2024'
        ]
        
        invalid_passwords = [
            'password',  # No uppercase, numbers, special chars
            'PASSWORD',  # No lowercase, numbers, special chars
            'Password',  # No numbers, special chars
            'Passw0rd',  # No special chars
            'Pass@1',  # Too short
            ''  # Empty
        ]
        
        for password in valid_passwords:
            assert re.match(PASSWORD_PATTERN, password), f"Should accept {password}"
        
        for password in invalid_passwords:
            assert not re.match(PASSWORD_PATTERN, password), f"Should reject {password}"

    def test_xss_patterns_coverage(self):
        """Test XSS patterns cover common attack vectors."""
        expected_patterns = [
            '<script', 'javascript:', 'onerror=', 'onclick=',
            '<iframe', 'document.', 'eval('
        ]
        
        for pattern in expected_patterns:
            assert pattern in XSS_PATTERNS
        
        # All patterns should be lowercase
        for pattern in XSS_PATTERNS:
            assert isinstance(pattern, str)
            assert pattern.islower()

    def test_content_filter_levels(self):
        """Test content filter levels are properly defined."""
        expected_levels = ['strict', 'moderate', 'basic']
        assert CONTENT_FILTER_LEVELS == expected_levels
        
        # Should be ordered from most to least restrictive
        assert CONTENT_FILTER_LEVELS[0] == 'strict'
        assert CONTENT_FILTER_LEVELS[-1] == 'basic'

    def test_age_limits_coppa_compliance(self):
        """Test age limits comply with COPPA requirements."""
        assert MIN_CHILD_AGE >= 2  # Reasonable minimum
        assert MAX_CHILD_AGE == 13  # COPPA limit
        assert COPPA_AGE_LIMIT == 13
        assert MIN_CHILD_AGE < MAX_CHILD_AGE

    def test_safety_thresholds(self):
        """Test safety thresholds are reasonable."""
        assert 0.0 <= DEFAULT_SAFETY_THRESHOLD <= 1.0
        assert DEFAULT_SAFETY_THRESHOLD >= 0.7  # Should be conservative


class TestRateLimitConfig:
    def test_get_rate_limit_config_with_production_config(self):
        """Test rate limit config uses production values when available."""
        mock_config = Mock()
        mock_config.RATE_LIMIT_REQUESTS_PER_MINUTE = 100
        mock_config.RATE_LIMIT_BURST = 20
        
        with patch('src.api.config.config', mock_config):
            result = get_rate_limit_config()
            
            assert result['per_minute'] == 100
            assert result['burst'] == 20

    def test_get_rate_limit_config_with_defaults(self):
        """Test rate limit config uses defaults when no production config."""
        with patch('src.api.config.config', None):
            result = get_rate_limit_config()
            
            assert 'per_minute' in result
            assert 'burst' in result
            assert isinstance(result['per_minute'], int)
            assert isinstance(result['burst'], int)
            assert result['per_minute'] > 0
            assert result['burst'] > 0

    def test_get_rate_limit_config_reasonable_defaults(self):
        """Test default rate limits are reasonable for child safety."""
        with patch('src.api.config.config', None):
            result = get_rate_limit_config()
            
            # Should allow reasonable usage but prevent abuse
            assert 30 <= result['per_minute'] <= 120
            assert 5 <= result['burst'] <= 30


class TestSafetyConfig:
    def test_get_safety_config_with_production_config(self):
        """Test safety config uses production values when available."""
        mock_config = Mock()
        mock_config.SAFETY_SCORE_THRESHOLD = 0.85
        mock_config.CONTENT_FILTER_STRICT = True
        mock_config.COPPA_COMPLIANCE_MODE = True
        
        with patch('src.api.config.config', mock_config):
            result = get_safety_config()
            
            assert result['threshold'] == 0.85
            assert result['strict_filtering'] is True
            assert result['coppa_mode'] is True

    def test_get_safety_config_with_defaults(self):
        """Test safety config uses safe defaults when no production config."""
        with patch('src.api.config.config', None):
            result = get_safety_config()
            
            assert 'threshold' in result
            assert 'strict_filtering' in result
            assert 'coppa_mode' in result
            
            # Defaults should be conservative for child safety
            assert result['threshold'] >= 0.7
            assert result['strict_filtering'] is True
            assert result['coppa_mode'] is True

    def test_get_safety_config_child_safety_defaults(self):
        """Test safety defaults prioritize child protection."""
        with patch('src.api.config.config', None):
            result = get_safety_config()
            
            # Should default to strictest settings
            assert result['threshold'] >= DEFAULT_SAFETY_THRESHOLD
            assert result['strict_filtering'] is True
            assert result['coppa_mode'] is True


class TestEnvironmentVariables:
    def test_api_constants_from_environment(self):
        """Test API constants can be overridden by environment variables."""
        with patch.dict(os.environ, {
            'API_TITLE': 'Test API',
            'API_VERSION': '2.0.0',
            'API_BASE_URL': 'https://test.example.com'
        }):
            # Re-import to get updated values
            import importlib
            import src.api.config
            importlib.reload(src.api.config)
            
            from src.api.config import API_TITLE, API_VERSION, API_BASE_URL
            
            assert API_TITLE == 'Test API'
            assert API_VERSION == '2.0.0'
            assert API_BASE_URL == 'https://test.example.com'

    def test_environment_defaults(self):
        """Test reasonable defaults when environment variables not set."""
        # Clear environment variables
        env_vars = ['API_TITLE', 'API_VERSION', 'API_BASE_URL', 'SUPPORT_EMAIL']
        
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.api.config
            importlib.reload(src.api.config)
            
            from src.api.config import API_TITLE, API_VERSION, API_BASE_URL, SUPPORT_EMAIL
            
            assert 'AI Teddy Bear' in API_TITLE
            assert API_VERSION.count('.') == 2  # Semantic versioning
            assert API_BASE_URL.startswith('https://')
            assert '@' in SUPPORT_EMAIL


class TestValidationPatterns:
    def test_phone_pattern_international_support(self):
        """Test phone pattern supports international formats."""
        import re
        
        international_phones = [
            '+1234567890',      # US
            '+441234567890',    # UK
            '+33123456789',     # France
            '+49123456789',     # Germany
            '+861234567890',    # China
            '+971234567890'     # UAE
        ]
        
        for phone in international_phones:
            assert re.match(PHONE_PATTERN, phone), f"Should support {phone}"

    def test_password_pattern_security_requirements(self):
        """Test password pattern enforces all security requirements."""
        import re
        
        # Test each requirement individually
        test_cases = [
            ('NoLowerCase123!', False),  # Missing lowercase
            ('nouppercase123!', False),  # Missing uppercase
            ('NoNumbers!', False),       # Missing numbers
            ('NoSpecialChars123', False), # Missing special chars
            ('Short1!', False),          # Too short
            ('ValidPass123!', True)      # Valid password
        ]
        
        for password, should_match in test_cases:
            result = bool(re.match(PASSWORD_PATTERN, password))
            assert result == should_match, f"Password '{password}' validation failed"

    def test_xss_pattern_detection(self):
        """Test XSS patterns detect common attack vectors."""
        malicious_inputs = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img onerror="alert(1)" src="x">',
            '<iframe src="javascript:alert(1)">',
            'document.cookie',
            'window.location',
            'eval("malicious code")'
        ]
        
        for malicious_input in malicious_inputs:
            input_lower = malicious_input.lower()
            detected = any(pattern in input_lower for pattern in XSS_PATTERNS)
            assert detected, f"Should detect XSS in: {malicious_input}"


class TestChildSafetyConstants:
    def test_inappropriate_words_child_protection(self):
        """Test inappropriate words protect child privacy."""
        privacy_categories = {
            'personal_info': ['password', 'email', 'phone', 'address'],
            'location': ['street', 'home address', 'school name'],
            'identity': ['last name', 'full name', 'birthday'],
            'unsafe_requests': ['meet up', 'come over', 'visit me']
        }
        
        for category, words in privacy_categories.items():
            for word in words:
                assert word in INAPPROPRIATE_WORDS, f"Missing {category} protection: {word}"

    def test_allowed_interests_age_appropriate(self):
        """Test allowed interests are age-appropriate for children."""
        child_appropriate = [
            'animals', 'dinosaurs', 'space', 'science', 'art',
            'music', 'books', 'nature', 'games', 'stories'
        ]
        
        for interest in child_appropriate:
            assert interest in ALLOWED_INTERESTS
        
        # Should not contain adult-oriented interests
        adult_topics = ['politics', 'finance', 'dating', 'alcohol']
        for topic in adult_topics:
            assert topic not in ALLOWED_INTERESTS

    def test_content_filter_levels_child_safety(self):
        """Test content filter levels prioritize child safety."""
        assert 'strict' in CONTENT_FILTER_LEVELS
        assert CONTENT_FILTER_LEVELS.index('strict') == 0  # Most restrictive first
        
        # Should have graduated levels
        assert len(CONTENT_FILTER_LEVELS) >= 3
        assert 'basic' in CONTENT_FILTER_LEVELS  # Least restrictive option


class TestConfigurationIntegrity:
    def test_age_limits_consistency(self):
        """Test age limits are internally consistent."""
        assert MIN_CHILD_AGE < MAX_CHILD_AGE
        assert MAX_CHILD_AGE <= COPPA_AGE_LIMIT
        assert MIN_CHILD_AGE >= 2  # Reasonable minimum for interaction

    def test_time_limits_reasonable(self):
        """Test time limits are reasonable for children."""
        from src.api.config import (
            MIN_CONVERSATION_TIME_LIMIT, MAX_CONVERSATION_TIME_LIMIT,
            MIN_DAILY_INTERACTION_LIMIT, MAX_DAILY_INTERACTION_LIMIT
        )
        
        # Conversation limits
        assert MIN_CONVERSATION_TIME_LIMIT >= 5  # At least 5 minutes
        assert MAX_CONVERSATION_TIME_LIMIT <= 120  # No more than 2 hours
        assert MIN_CONVERSATION_TIME_LIMIT < MAX_CONVERSATION_TIME_LIMIT
        
        # Daily limits
        assert MIN_DAILY_INTERACTION_LIMIT >= 15  # At least 15 minutes
        assert MAX_DAILY_INTERACTION_LIMIT <= 360  # No more than 6 hours
        assert MIN_DAILY_INTERACTION_LIMIT < MAX_DAILY_INTERACTION_LIMIT

    def test_safety_thresholds_conservative(self):
        """Test safety thresholds are conservative for child protection."""
        from src.api.config import MIN_SAFETY_SCORE, MAX_SAFETY_SCORE
        
        assert MIN_SAFETY_SCORE == 0.0
        assert MAX_SAFETY_SCORE == 1.0
        assert DEFAULT_SAFETY_THRESHOLD >= 0.8  # Conservative default

    def test_supported_languages_practical(self):
        """Test supported languages cover major user bases."""
        # Should include major world languages
        major_languages = ['en', 'es', 'zh', 'ar', 'fr']
        for lang in major_languages:
            assert lang in SUPPORTED_LANGUAGES
        
        # Should have reasonable coverage without being overwhelming
        assert 8 <= len(SUPPORTED_LANGUAGES) <= 20


class TestSecurityConfiguration:
    def test_xss_protection_comprehensive(self):
        """Test XSS protection covers major attack vectors."""
        attack_categories = {
            'script_injection': ['<script', '</script>', 'javascript:'],
            'event_handlers': ['onerror=', 'onload=', 'onclick='],
            'dom_manipulation': ['document.', 'window.', 'eval('],
            'embedded_content': ['<iframe', '<object', '<embed']
        }
        
        for category, patterns in attack_categories.items():
            for pattern in patterns:
                assert pattern in XSS_PATTERNS, f"Missing {category} protection: {pattern}"

    def test_password_requirements_strong(self):
        """Test password requirements enforce strong security."""
        import re
        
        # Should require all character types
        weak_passwords = [
            'alllowercase',      # No uppercase, numbers, special
            'ALLUPPERCASE',      # No lowercase, numbers, special
            'NoSpecialChars123', # No special characters
            'NoNumbers!',        # No numbers
            'Short1!'           # Too short
        ]
        
        for password in weak_passwords:
            assert not re.match(PASSWORD_PATTERN, password), f"Should reject weak password: {password}"

    def test_inappropriate_content_detection(self):
        """Test inappropriate content detection is comprehensive."""
        # Should detect attempts to share personal information
        personal_info_attempts = [
            'my password is secret123',
            'I live on main street',
            'call me at 555-1234',
            'email me at child@example.com'
        ]
        
        for attempt in personal_info_attempts:
            attempt_lower = attempt.lower()
            detected = any(word in attempt_lower for word in INAPPROPRIATE_WORDS)
            assert detected, f"Should detect personal info in: {attempt}"