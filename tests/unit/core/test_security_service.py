"""
Comprehensive unit tests for core security service with 100% coverage.
Tests threat detection, security validation, COPPA compliance, and content safety.
"""

import pytest
import time
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from dataclasses import asdict
from sqlalchemy.exc import SQLAlchemyError

from src.core.security_service import (
    SecurityThreat,
    ThreatDetector,
    SecurityService,
    create_security_service,
    MLAnomalyDetector,
    BehaviorFeatures,
    AnomalyResult,
)
from src.infrastructure.rate_limiting.rate_limiter import (
    RateLimitingService,
    OperationType,
    RateLimitResult,
    create_memory_rate_limiting_service
)


class TestSecurityThreat:
    """Test SecurityThreat dataclass."""

    def test_security_threat_creation(self):
        """Test SecurityThreat creation with required fields."""
        threat = SecurityThreat(
            threat_id="test_threat_123",
            threat_type="brute_force_attack",
            severity="high",
            description="Test threat description",
            detected_at=datetime.utcnow()
        )
        
        assert threat.threat_id == "test_threat_123"
        assert threat.threat_type == "brute_force_attack"
        assert threat.severity == "high"
        assert threat.description == "Test threat description"
        assert isinstance(threat.detected_at, datetime)
        assert threat.source_ip is None
        assert threat.user_id is None
        assert threat.metadata is None

    def test_security_threat_with_optional_fields(self):
        """Test SecurityThreat creation with optional fields."""
        metadata = {"attempt_count": 5, "time_window": "1_hour"}
        threat = SecurityThreat(
            threat_id="test_threat_456",
            threat_type="suspicious_access",
            severity="medium",
            description="Suspicious activity detected",
            detected_at=datetime.utcnow(),
            source_ip="192.168.1.100",
            user_id="user_123",
            metadata=metadata
        )
        
        assert threat.source_ip == "192.168.1.100"
        assert threat.user_id == "user_123"
        assert threat.metadata == metadata

    def test_security_threat_severity_levels(self):
        """Test different severity levels."""
        severities = ["low", "medium", "high", "critical"]
        
        for severity in severities:
            threat = SecurityThreat(
                threat_id=f"threat_{severity}",
                threat_type="test_type",
                severity=severity,
                description="Test description",
                detected_at=datetime.utcnow()
            )
            assert threat.severity == severity

    def test_security_threat_serializable(self):
        """Test that SecurityThreat can be converted to dict."""
        threat = SecurityThreat(
            threat_id="test_threat",
            threat_type="test_type",
            severity="high",
            description="Test description",
            detected_at=datetime.utcnow(),
            source_ip="127.0.0.1",
            metadata={"key": "value"}
        )
        
        threat_dict = asdict(threat)
        assert isinstance(threat_dict, dict)
        assert threat_dict["threat_id"] == "test_threat"
        assert threat_dict["source_ip"] == "127.0.0.1"


class TestThreatDetector:
    """Test ThreatDetector class."""

    @pytest.fixture
    def threat_detector(self):
        """Create ThreatDetector instance for testing."""
        with patch('src.core.security_service.get_logger'):
            return ThreatDetector()

    def test_threat_detector_initialization(self, threat_detector):
        """Test ThreatDetector initialization."""
        assert hasattr(threat_detector, 'logger')
        assert isinstance(threat_detector.failed_attempts, dict)
        assert isinstance(threat_detector.suspicious_patterns, dict)

    def test_detect_brute_force_no_threat(self, threat_detector):
        """Test brute force detection with normal activity."""
        with patch('time.time', return_value=1000.0):
            threat = threat_detector.detect_brute_force("192.168.1.1", "user123")
            
            assert threat is None
            assert "192.168.1.1" in threat_detector.failed_attempts
            assert len(threat_detector.failed_attempts["192.168.1.1"]) == 1

    def test_detect_brute_force_threat_detected(self, threat_detector):
        """Test brute force detection when threat is detected."""
        ip_address = "192.168.1.100"
        
        with patch('time.time', return_value=1000.0):
            # Simulate 10 failed attempts
            for i in range(10):
                threat = threat_detector.detect_brute_force(ip_address, "user123")
            
            assert threat is not None
            assert threat.threat_type == "brute_force_attack"
            assert threat.severity == "high"
            assert threat.source_ip == ip_address
            assert threat.user_id == "user123"
            assert threat.metadata["attempt_count"] == 10
            assert "brute_force_" in threat.threat_id

    def test_detect_brute_force_old_attempts_cleaned(self, threat_detector):
        """Test that old brute force attempts are cleaned up."""
        ip_address = "192.168.1.200"
        
        # Add old attempts (more than 1 hour ago)
        with patch('time.time', return_value=1000.0):
            for i in range(5):
                threat_detector.detect_brute_force(ip_address)
        
        # Add recent attempts
        with patch('time.time', return_value=5000.0):  # 4000 seconds later
            for i in range(3):
                threat = threat_detector.detect_brute_force(ip_address)
        
            # Should only count recent attempts
            assert threat is None
            assert len(threat_detector.failed_attempts[ip_address]) == 3

    def test_detect_brute_force_multiple_ips(self, threat_detector):
        """Test brute force detection with multiple IP addresses."""
        with patch('time.time', return_value=1000.0):
            # Test that attempts are tracked separately per IP
            threat_detector.detect_brute_force("192.168.1.1")
            threat_detector.detect_brute_force("192.168.1.2")
            
            assert len(threat_detector.failed_attempts) == 2
            assert len(threat_detector.failed_attempts["192.168.1.1"]) == 1
            assert len(threat_detector.failed_attempts["192.168.1.2"]) == 1

    def test_detect_brute_force_no_user_id(self, threat_detector):
        """Test brute force detection without user_id."""
        with patch('time.time', return_value=1000.0):
            for i in range(10):
                threat = threat_detector.detect_brute_force("192.168.1.50")
            
            assert threat is not None
            assert threat.user_id is None
            assert threat.source_ip == "192.168.1.50"

    def test_detect_suspicious_child_access_no_threat(self, threat_detector):
        """Test suspicious child access detection with normal patterns."""
        access_pattern = {
            "access_count": 5,
            "access_frequency": 2,
            "unusual_hours": False
        }
        
        threat = threat_detector.detect_suspicious_child_access(
            "parent123", "child456", access_pattern
        )
        
        assert threat is None

    def test_detect_suspicious_child_access_excessive_count(self, threat_detector):
        """Test detection of excessive access count."""
        access_pattern = {
            "access_count": 100,
            "access_frequency": 5,
            "unusual_hours": False
        }
        
        threat = threat_detector.detect_suspicious_child_access(
            "parent123", "child456", access_pattern
        )
        
        assert threat is not None
        assert threat.threat_type == "suspicious_child_data_access"
        assert threat.severity == "medium"
        assert "excessive_access_count" in threat.metadata["threat_indicators"]

    def test_detect_suspicious_child_access_high_frequency(self, threat_detector):
        """Test detection of high frequency access."""
        access_pattern = {
            "access_count": 10,
            "access_frequency": 15,
            "unusual_hours": False
        }
        
        threat = threat_detector.detect_suspicious_child_access(
            "parent123", "child456", access_pattern
        )
        
        assert threat is not None
        assert "high_frequency_access" in threat.metadata["threat_indicators"]

    def test_detect_suspicious_child_access_unusual_hours(self, threat_detector):
        """Test detection of unusual hours access."""
        access_pattern = {
            "access_count": 10,
            "access_frequency": 5,
            "unusual_hours": True
        }
        
        threat = threat_detector.detect_suspicious_child_access(
            "parent123", "child456", access_pattern
        )
        
        assert threat is not None
        assert "unusual_time_access" in threat.metadata["threat_indicators"]

    def test_detect_suspicious_child_access_multiple_indicators(self, threat_detector):
        """Test detection with multiple suspicious indicators."""
        access_pattern = {
            "access_count": 100,
            "access_frequency": 15,
            "unusual_hours": True
        }
        
        threat = threat_detector.detect_suspicious_child_access(
            "parent123", "child456", access_pattern
        )
        
        assert threat is not None
        assert threat.severity == "critical"  # Multiple indicators = critical
        assert len(threat.metadata["threat_indicators"]) == 3
        assert "excessive_access_count" in threat.metadata["threat_indicators"]
        assert "high_frequency_access" in threat.metadata["threat_indicators"]
        assert "unusual_time_access" in threat.metadata["threat_indicators"]

    def test_detect_suspicious_child_access_child_id_hashed(self, threat_detector):
        """Test that child ID is properly hashed in metadata."""
        access_pattern = {"access_count": 100}
        child_id = "sensitive_child_id_123"
        
        threat = threat_detector.detect_suspicious_child_access(
            "parent123", child_id, access_pattern
        )
        
        expected_hash = hashlib.sha256(child_id.encode()).hexdigest()[:16]
        assert threat.metadata["child_id_hash"] == expected_hash
        assert child_id not in str(threat.metadata)  # Ensure child ID not exposed

    def test_detect_content_injection_no_threat(self, threat_detector):
        """Test content injection detection with safe content."""
        safe_content = "Hello, how are you today? I love playing with toys!"
        
        threat = threat_detector.detect_content_injection(safe_content, "user123")
        
        assert threat is None

    def test_detect_content_injection_script_injection(self, threat_detector):
        """Test detection of script injection attempts."""
        malicious_content = "Hello <script>alert('XSS')</script> world"
        
        threat = threat_detector.detect_content_injection(malicious_content, "user123")
        
        assert threat is not None
        assert threat.threat_type == "content_injection_attempt"
        assert threat.severity == "high"
        assert "<script" in threat.metadata["detected_patterns"]
        assert "alert(" in threat.metadata["detected_patterns"]

    def test_detect_content_injection_sql_injection(self, threat_detector):
        """Test detection of SQL injection attempts."""
        malicious_content = "user'; DROP TABLE users; --"
        
        threat = threat_detector.detect_content_injection(malicious_content, "user123")
        
        assert threat is not None
        assert "DROP TABLE" in threat.metadata["detected_patterns"]

    def test_detect_content_injection_multiple_patterns(self, threat_detector):
        """Test detection with multiple injection patterns."""
        malicious_content = "Test javascript:alert(1) and SELECT * FROM users"
        
        threat = threat_detector.detect_content_injection(malicious_content, "user123")
        
        assert threat is not None
        assert len(threat.metadata["detected_patterns"]) >= 2
        assert "javascript:" in threat.metadata["detected_patterns"]
        assert "SELECT * FROM" in threat.metadata["detected_patterns"]

    def test_detect_content_injection_case_insensitive(self, threat_detector):
        """Test that content injection detection is case insensitive."""
        malicious_content = "Test JAVASCRIPT:ALERT(1) and select * from users"
        
        threat = threat_detector.detect_content_injection(malicious_content, "user123")
        
        assert threat is not None
        assert len(threat.metadata["detected_patterns"]) >= 2

    def test_detect_content_injection_content_metadata(self, threat_detector):
        """Test that content metadata is properly included."""
        malicious_content = "Test <script>alert(1)</script>"
        
        threat = threat_detector.detect_content_injection(malicious_content, "user123")
        
        assert threat.metadata["content_length"] == len(malicious_content)
        expected_hash = hashlib.sha256(malicious_content.encode()).hexdigest()[:16]
        assert threat.metadata["content_hash"] == expected_hash

    def test_detect_content_injection_no_user_id(self, threat_detector):
        """Test content injection detection without user_id."""
        malicious_content = "Test <script>alert(1)</script>"
        
        threat = threat_detector.detect_content_injection(malicious_content)
        
        assert threat is not None
        assert threat.user_id is None

    def test_detect_content_injection_all_patterns(self, threat_detector):
        """Test detection of all injection patterns."""
        patterns = [
            "<script", "javascript:", "onload=", "onerror=", "eval(",
            "document.cookie", "window.location", "alert(", "prompt(", "confirm(",
            "DROP TABLE", "SELECT * FROM", "UNION SELECT", "INSERT INTO",
            "UPDATE SET", "DELETE FROM"
        ]
        
        for pattern in patterns:
            content = f"Test content with {pattern} injection"
            threat = threat_detector.detect_content_injection(content)
            assert threat is not None
            assert pattern in threat.metadata["detected_patterns"]


class TestSecurityService:
    """Test SecurityService class."""

    @pytest.fixture
    def mock_rate_limiting_service(self):
        """Create mock rate limiting service."""
        return Mock()

    @pytest.fixture
    def security_service(self, mock_rate_limiting_service):
        """Create SecurityService instance for testing."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService(mock_rate_limiting_service)

    def test_security_service_initialization(self, security_service):
        """Test SecurityService initialization."""
        assert hasattr(security_service, 'logger')
        assert isinstance(security_service.threat_detector, ThreatDetector)
        assert isinstance(security_service.active_threats, list)
        assert isinstance(security_service.blocked_ips, set)
        assert isinstance(security_service.security_events, list)

    @pytest.mark.asyncio
    async def test_verify_parent_child_relationship_success(self):
        """Test successful parent-child relationship verification."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.initialize_database') as mock_init:
            
            # Mock database manager and session
            mock_db_manager = AsyncMock()
            mock_session = AsyncMock()
            mock_result = AsyncMock()
            mock_row = Mock()
            
            mock_init.return_value = mock_db_manager
            mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session
            mock_session.execute.return_value = mock_result
            mock_result.first.return_value = mock_row
            
            service = SecurityService()
            result = await service.verify_parent_child_relationship("parent123", "child456")
            
            assert result is True
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_parent_child_relationship_not_found(self):
        """Test parent-child relationship verification when not found."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.initialize_database') as mock_init:
            
            mock_db_manager = AsyncMock()
            mock_session = AsyncMock()
            mock_result = AsyncMock()
            
            mock_init.return_value = mock_db_manager
            mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session
            mock_session.execute.return_value = mock_result
            mock_result.first.return_value = None
            
            service = SecurityService()
            result = await service.verify_parent_child_relationship("parent123", "child456")
            
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_parent_child_relationship_database_error(self):
        """Test parent-child relationship verification with database error."""
        with patch('src.core.security_service.get_logger') as mock_logger, \
             patch('src.core.security_service.initialize_database') as mock_init:
            
            mock_db_manager = AsyncMock()
            mock_session = AsyncMock()
            
            mock_init.return_value = mock_db_manager
            mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session
            mock_session.execute.side_effect = SQLAlchemyError("Database error")
            
            service = SecurityService()
            result = await service.verify_parent_child_relationship("parent123", "child456")
            
            assert result is False
            mock_logger.return_value.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_request_security_safe_request(self, security_service):
        """Test validation of safe request."""
        request_data = {
            "message": "Hello, how are you?",
            "user_id": "user123"
        }
        user_context = {
            "user_id": "user123",
            "ip_address": "192.168.1.1"
        }
        
        result = await security_service.validate_request_security(request_data, user_context)
        
        assert result["is_safe"] is True
        assert result["security_score"] == 1.0
        assert len(result["threats_detected"]) == 0
        assert len(result["recommendations"]) == 0

    @pytest.mark.asyncio
    async def test_validate_request_security_content_injection(self, security_service):
        """Test validation with content injection threat."""
        request_data = {
            "content": "Hello <script>alert('XSS')</script>",
            "user_id": "user123"
        }
        user_context = {
            "user_id": "user123",
            "ip_address": "192.168.1.1"
        }
        
        with patch('src.core.security_service.security_logger') as mock_logger, \
             patch('src.core.security_service.coppa_audit') as mock_audit:
            
            result = await security_service.validate_request_security(request_data, user_context)
            
            assert result["is_safe"] is False
            assert result["security_score"] == 0.1  # Multiplied by 0.1
            assert len(result["threats_detected"]) == 1
            assert result["threats_detected"][0].threat_type == "content_injection_attempt"
            
            # Verify logging
            mock_logger.warning.assert_called_once()
            mock_audit.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_request_security_brute_force(self, security_service):
        """Test validation with brute force detection."""
        request_data = {
            "authentication_failed": True,
            "user_id": "user123"
        }
        user_context = {
            "user_id": "user123",
            "ip_address": "192.168.1.100"
        }
        
        # Simulate multiple failed attempts to trigger brute force detection
        with patch.object(security_service.threat_detector, 'detect_brute_force') as mock_detect:
            mock_threat = SecurityThreat(
                threat_id="brute_force_123",
                threat_type="brute_force_attack",
                severity="high",
                description="Brute force detected",
                detected_at=datetime.utcnow(),
                source_ip="192.168.1.100"
            )
            mock_detect.return_value = mock_threat
            
            result = await security_service.validate_request_security(request_data, user_context)
            
            assert result["is_safe"] is False
            assert result["security_score"] == 0.2  # Multiplied by 0.2
            assert len(result["threats_detected"]) == 1
            assert "ip_blocked" in result["recommendations"]
            assert "192.168.1.100" in security_service.blocked_ips

    @pytest.mark.asyncio
    async def test_validate_request_security_no_user_context(self, security_service):
        """Test validation without user context."""
        request_data = {
            "content": "Safe content",
        }
        
        result = await security_service.validate_request_security(request_data)
        
        assert result["is_safe"] is True
        assert result["security_score"] == 1.0

    @pytest.mark.asyncio
    async def test_validate_request_security_brute_force_medium_severity(self, security_service):
        """Test brute force detection with medium severity doesn't block IP."""
        request_data = {
            "authentication_failed": True,
            "user_id": "user123"
        }
        user_context = {
            "user_id": "user123",
            "ip_address": "192.168.1.200"
        }
        
        with patch.object(security_service.threat_detector, 'detect_brute_force') as mock_detect:
            mock_threat = SecurityThreat(
                threat_id="brute_force_123",
                threat_type="brute_force_attack",
                severity="medium",  # Not high severity
                description="Brute force detected",
                detected_at=datetime.utcnow(),
                source_ip="192.168.1.200"
            )
            mock_detect.return_value = mock_threat
            
            result = await security_service.validate_request_security(request_data, user_context)
            
            assert result["is_safe"] is False
            assert "ip_blocked" not in result["recommendations"]
            assert "192.168.1.200" not in security_service.blocked_ips

    @pytest.mark.asyncio
    async def test_validate_child_data_access_child_own_data(self, security_service):
        """Test child accessing their own data."""
        user_context = {"user_type": "child"}
        
        with patch('src.core.security_service.coppa_audit') as mock_audit:
            result = await security_service.validate_child_data_access(
                "child123", "child123", "read", user_context
            )
            
            assert result["access_allowed"] is True
            assert result["coppa_compliant"] is True
            assert result["audit_required"] is True
            assert len(result["restrictions"]) == 0
            
            # Verify audit logging
            mock_audit.log_event.assert_called_once()
            call_args = mock_audit.log_event.call_args[0][0]
            assert call_args["event_type"] == "child_data_access"

    @pytest.mark.asyncio
    async def test_validate_child_data_access_child_other_data(self, security_service):
        """Test child trying to access other child's data."""
        user_context = {"user_type": "child"}
        
        with patch('src.core.security_service.security_logger') as mock_logger:
            result = await security_service.validate_child_data_access(
                "child123", "child456", "read", user_context
            )
            
            assert result["access_allowed"] is False
            assert "child_can_only_access_own_data" in result["restrictions"]
            
            # Verify security logging
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_child_data_access_parent_valid(self, security_service):
        """Test parent accessing child data with valid relationship."""
        user_context = {"user_type": "parent"}
        
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=True), \
             patch('src.core.security_service.coppa_audit') as mock_audit:
            
            result = await security_service.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
            
            assert result["access_allowed"] is True
            assert result["coppa_compliant"] is True

    @pytest.mark.asyncio
    async def test_validate_child_data_access_parent_invalid(self, security_service):
        """Test parent accessing child data with invalid relationship."""
        user_context = {"user_type": "parent"}
        
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=False), \
             patch('src.core.security_service.security_logger') as mock_logger:
            
            result = await security_service.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
            
            assert result["access_allowed"] is False
            assert "parent_child_relationship_invalid" in result["restrictions"]

    @pytest.mark.asyncio
    async def test_validate_child_data_access_admin(self, security_service):
        """Test admin accessing child data."""
        user_context = {"user_type": "admin"}
        
        result = await security_service.validate_child_data_access(
            "admin123", "child456", "read", user_context
        )
        
        assert result["access_allowed"] is True

    @pytest.mark.asyncio
    async def test_validate_child_data_access_system(self, security_service):
        """Test system accessing child data."""
        user_context = {"user_type": "system"}
        
        result = await security_service.validate_child_data_access(
            "system123", "child456", "read", user_context
        )
        
        assert result["access_allowed"] is True

    @pytest.mark.asyncio
    async def test_validate_child_data_access_unauthorized(self, security_service):
        """Test unauthorized user accessing child data."""
        user_context = {"user_type": "unknown"}
        
        result = await security_service.validate_child_data_access(
            "unknown123", "child456", "read", user_context
        )
        
        assert result["access_allowed"] is False
        assert "unauthorized_user_role" in result["restrictions"]

    @pytest.mark.asyncio  
    async def test_validate_child_data_access_no_context(self, security_service):
        """Test child data access validation without user context."""
        result = await security_service.validate_child_data_access(
            "user123", "child456", "read"
        )
        
        assert result["access_allowed"] is False
        assert "unauthorized_user_role" in result["restrictions"]

    @pytest.mark.asyncio
    async def test_validate_child_data_access_pattern_analysis(self, security_service):
        """Test access pattern analysis functionality."""
        user_context = {
            "user_type": "parent",
            "ip_address": "192.168.1.1"
        }
        
        # Mock the verify_parent_child_relationship to return True
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=True), \
             patch('src.core.security_service.coppa_audit'):
            
            # Simulate multiple accesses to build pattern
            for i in range(35):  # Exceed hourly threshold
                await security_service.validate_child_data_access(
                    "parent123", "child456", "read", user_context
                )
            
            # Check that access logs are being maintained
            log_key = "parent123:child456:parent"
            assert log_key in security_service._access_logs
            assert len(security_service._access_logs[log_key]) <= 500  # Max limit

    @pytest.mark.asyncio
    async def test_validate_child_data_access_suspicious_pattern_detected(self, security_service):
        """Test detection of suspicious access patterns."""
        user_context = {
            "user_type": "parent",
            "ip_address": "192.168.1.1"
        }
        
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=True), \
             patch('src.core.security_service.coppa_audit') as mock_audit, \
             patch('src.core.security_service.security_logger') as mock_logger:
            
            # Simulate excessive access pattern
            # First, fill up the access log with many entries to trigger suspicious pattern
            log_key = "parent123:child456:parent"
            now = datetime.utcnow()
            
            # Add many recent accesses to trigger suspicious behavior detection
            security_service._access_logs[log_key] = []
            for i in range(31):  # Exceed hourly threshold
                security_service._access_logs[log_key].append({
                    "timestamp": now - timedelta(minutes=i),
                    "access_type": "read",
                    "ip_address": "192.168.1.1"
                })
            
            result = await security_service.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
            
            # Should detect suspicious pattern and deny access
            assert result["access_allowed"] is False
            assert "suspicious_access_pattern_detected" in result["restrictions"]
            assert result["coppa_compliant"] is False

    @pytest.mark.asyncio
    async def test_validate_child_data_access_unusual_hours(self, security_service):
        """Test detection of unusual hours access."""
        user_context = {
            "user_type": "parent",
            "ip_address": "192.168.1.1"
        }
        
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=True), \
             patch('src.core.security_service.coppa_audit') as mock_audit:
            
            # Mock current time to be in unusual hours (2 AM)
            with patch('src.core.security_service.datetime') as mock_datetime:
                unusual_time = datetime.utcnow().replace(hour=2, minute=0, second=0, microsecond=0)
                mock_datetime.utcnow.return_value = unusual_time
                
                result = await security_service.validate_child_data_access(
                    "parent123", "child456", "read", user_context
                )
                
                # Should log suspicious activity for unusual hours
                mock_audit.log_event.assert_called()
                # Check if any call includes suspicious activity
                suspicious_calls = [call for call in mock_audit.log_event.call_args_list 
                                  if call[0][0].get("event_type") == "suspicious_activity"]
                assert len(suspicious_calls) >= 1

    @pytest.mark.asyncio
    async def test_check_content_safety_safe_content(self, security_service):
        """Test content safety check with safe content."""
        safe_content = "Hello! Let's learn about dinosaurs. They were amazing creatures!"
        
        result = await security_service.check_content_safety(safe_content, child_age=8)
        
        assert result["is_safe"] is True
        assert result["safety_score"] == 1.0
        assert len(result["violations"]) == 0
        assert result["filtered_content"] == safe_content
        assert result["age_appropriate"] is True

    @pytest.mark.asyncio
    async def test_check_content_safety_unsafe_content(self, security_service):
        """Test content safety check with unsafe content."""
        unsafe_content = "Let's talk about violence and weapons like guns and knives"
        
        with patch('src.core.security_service.security_logger') as mock_logger, \
             patch('src.core.security_service.coppa_audit') as mock_audit:
            
            result = await security_service.check_content_safety(unsafe_content, child_age=8)
            
            assert result["is_safe"] is False
            assert result["safety_score"] < 1.0
            assert len(result["violations"]) > 0
            assert "gun" in result["violations"]
            assert "knife" in result["violations"]
            assert "***" in result["filtered_content"]  # Content should be filtered
            
            # Verify logging
            mock_logger.warning.assert_called_once()
            mock_audit.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_content_safety_personal_info_request(self, security_service):
        """Test detection of personal information requests."""
        unsafe_content = "What's your address and phone number?"
        
        result = await security_service.check_content_safety(unsafe_content, child_age=8)
        
        assert result["is_safe"] is False
        assert "address" in result["violations"]
        assert "phone number" in result["violations"]

    @pytest.mark.asyncio
    async def test_check_content_safety_all_unsafe_patterns(self, security_service):
        """Test detection of all unsafe patterns."""
        patterns = [
            "kill", "murder", "blood", "weapon", "gun", "knife",
            "sex", "adult", "mature", "explicit",
            "address", "phone number", "email", "password",
            "meet me", "come to", "visit me", "secret"
        ]
        
        for pattern in patterns:
            content = f"Test content with {pattern} in it"
            result = await security_service.check_content_safety(content, child_age=8)
            assert result["is_safe"] is False
            assert pattern in result["violations"]

    @pytest.mark.asyncio
    async def test_check_content_safety_age_inappropriate(self, security_service):
        """Test age-inappropriate content detection."""
        content = "This might be scary and frightening for you"
        
        result = await security_service.check_content_safety(content, child_age=5)
        
        assert result["age_appropriate"] is False
        assert result["safety_score"] < 1.0

    @pytest.mark.asyncio
    async def test_check_content_safety_age_inappropriate_patterns(self, security_service):
        """Test all age-inappropriate patterns."""
        patterns = ["scary", "frightening", "nightmare"]
        
        for pattern in patterns:
            content = f"This might be {pattern} for children"
            result = await security_service.check_content_safety(content, child_age=10)
            assert result["age_appropriate"] is False

    @pytest.mark.asyncio
    async def test_check_content_safety_no_age_provided(self, security_service):
        """Test content safety check without age provided."""
        content = "This might be scary"
        
        result = await security_service.check_content_safety(content)
        
        # Should not perform age-specific checks
        assert result["age_appropriate"] is True

    @pytest.mark.asyncio
    async def test_check_content_safety_scoring(self, security_service):
        """Test content safety scoring calculation."""
        # Content with 3 violations should have score = 1.0 - (3 * 0.2) = 0.4
        unsafe_content = "gun knife blood"
        
        result = await security_service.check_content_safety(unsafe_content)
        
        expected_score = max(0.1, 1.0 - (3 * 0.2))
        assert result["safety_score"] == expected_score

    @pytest.mark.asyncio
    async def test_check_content_safety_many_violations(self, security_service):
        """Test content safety with many violations hits minimum score."""
        # Content with many violations should hit minimum score of 0.1
        unsafe_content = "gun knife blood murder kill weapon adult explicit"
        
        result = await security_service.check_content_safety(unsafe_content)
        
        assert result["safety_score"] == 0.1  # Minimum score

    @pytest.mark.asyncio
    async def test_check_content_safety_content_filtering(self, security_service):
        """Test that content is properly filtered."""
        unsafe_content = "Let's use a gun and knife"
        
        result = await security_service.check_content_safety(unsafe_content)
        
        # Both violations should be replaced with ***
        assert "gun" not in result["filtered_content"]
        assert "knife" not in result["filtered_content"]
        assert result["filtered_content"].count("***") == 2

    @pytest.mark.asyncio
    async def test_health_check(self, security_service):
        """Test security service health check."""
        # Add some test data
        security_service.active_threats = ["threat1", "threat2"]
        security_service.blocked_ips = {"192.168.1.1", "10.0.0.1"}
        security_service.security_events = [
            {"timestamp": time.time() - 1000},  # Recent event
            {"timestamp": time.time() - 100000}  # Old event
        ]
        
        result = await security_service.health_check()
        
        assert result["status"] == "healthy"
        assert result["active_threats"] == 2
        assert result["blocked_ips"] == 2
        assert result["security_events_24h"] == 1  # Only recent event
        assert result["threat_detection"] == "active"
        assert result["content_filtering"] == "active"

    @pytest.mark.asyncio
    async def test_health_check_no_recent_events(self, security_service):
        """Test health check with no recent events."""
        security_service.security_events = [
            {"timestamp": time.time() - 100000}  # Old event only
        ]
        
        result = await security_service.health_check()
        
        assert result["security_events_24h"] == 0

    @pytest.mark.asyncio
    async def test_health_check_events_without_timestamp(self, security_service):
        """Test health check with events missing timestamp."""
        security_service.security_events = [
            {"data": "event_without_timestamp"}
        ]
        
        result = await security_service.health_check()
        
        # Events without timestamp should be treated as old (default 0)
        assert result["security_events_24h"] == 0

    def test_is_ip_blocked(self, security_service):
        """Test IP blocking check."""
        ip_address = "192.168.1.100"
        
        # Initially not blocked
        assert security_service.is_ip_blocked(ip_address) is False
        
        # Add to blocked IPs
        security_service.blocked_ips.add(ip_address)
        assert security_service.is_ip_blocked(ip_address) is True

    def test_block_ip(self, security_service):
        """Test IP blocking functionality."""
        ip_address = "192.168.1.200"
        reason = "brute_force_attack"
        
        with patch('src.core.security_service.security_logger') as mock_logger, \
             patch('src.core.security_service.coppa_audit') as mock_audit:
            
            security_service.block_ip(ip_address, reason)
            
            assert ip_address in security_service.blocked_ips
            
            # Verify logging
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "IP address blocked"
            
            # Verify audit logging
            mock_audit.log_event.assert_called_once()
            audit_args = mock_audit.log_event.call_args[0][0]
            assert audit_args["event_type"] == "ip_blocked"
            assert audit_args["metadata"]["ip_address"] == ip_address
            assert audit_args["metadata"]["reason"] == reason

    def test_block_ip_default_reason(self, security_service):
        """Test IP blocking with default reason."""
        ip_address = "192.168.1.300"
        
        with patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit') as mock_audit:
            
            security_service.block_ip(ip_address)
            
            audit_args = mock_audit.log_event.call_args[0][0]
            assert audit_args["metadata"]["reason"] == "security_violation"


class TestCreateSecurityService:
    """Test security service factory function."""

    def test_create_security_service_no_rate_limiting(self):
        """Test creating security service without rate limiting."""
        with patch('src.core.security_service.get_logger'):
            service = create_security_service()
            
            assert isinstance(service, SecurityService)
            assert service.rate_limiting_service is None

    def test_create_security_service_with_rate_limiting(self):
        """Test creating security service with rate limiting."""
        mock_rate_limiting = Mock()
        
        with patch('src.core.security_service.get_logger'):
            service = create_security_service(mock_rate_limiting)
            
            assert isinstance(service, SecurityService)
            assert service.rate_limiting_service is mock_rate_limiting


class TestSecurityServiceIntegration:
    """Test integration scenarios for SecurityService."""

    @pytest.fixture
    def security_service(self):
        """Create SecurityService for integration testing."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService()

    @pytest.mark.asyncio
    async def test_complete_security_validation_workflow(self, security_service):
        """Test complete security validation workflow."""
        # Simulate a malicious request
        request_data = {
            "content": "Hello <script>alert('XSS')</script>",
            "authentication_failed": True
        }
        user_context = {
            "user_id": "attacker123",
            "ip_address": "192.168.1.100"
        }
        
        # First validation - should detect content injection
        result1 = await security_service.validate_request_security(request_data, user_context)
        assert result1["is_safe"] is False
        
        # Simulate multiple failed authentication attempts
        for i in range(10):
            request_data_auth = {"authentication_failed": True}
            result = await security_service.validate_request_security(
                request_data_auth, user_context
            )
        
        # IP should be blocked after brute force detection
        assert security_service.is_ip_blocked("192.168.1.100")
        
        # Health check should show activity
        health = await security_service.health_check()
        assert health["blocked_ips"] >= 1

    @pytest.mark.asyncio
    async def test_child_safety_workflow(self, security_service):
        """Test complete child safety workflow."""
        # Test child data access validation
        child_context = {"user_type": "child"}
        access_result = await security_service.validate_child_data_access(
            "child123", "child123", "read", child_context
        )
        assert access_result["access_allowed"] is True
        
        # Test content safety for child
        unsafe_content = "Let's meet in person and share your address"
        safety_result = await security_service.check_content_safety(
            unsafe_content, child_age=8
        )
        assert safety_result["is_safe"] is False
        assert "address" in safety_result["violations"]

    @pytest.mark.asyncio
    async def test_multiple_threat_detection(self, security_service):
        """Test detection of multiple threats in single request."""
        malicious_request = {
            "content": "Hello <script>alert(1)</script> what's your phone number?",
            "authentication_failed": True
        }
        user_context = {
            "user_id": "attacker",
            "ip_address": "10.0.0.1"
        }
        
        # Trigger brute force detection
        with patch.object(security_service.threat_detector, 'detect_brute_force') as mock_bf:
            mock_bf.return_value = SecurityThreat(
                threat_id="bf_123", threat_type="brute_force_attack",
                severity="high", description="Brute force",
                detected_at=datetime.utcnow()
            )
            
            result = await security_service.validate_request_security(
                malicious_request, user_context
            )
            
            # Should detect both content injection and brute force
            assert len(result["threats_detected"]) == 2
            threat_types = [t.threat_type for t in result["threats_detected"]]
            assert "content_injection_attempt" in threat_types
            assert "brute_force_attack" in threat_types


class TestSecurityServiceEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def security_service(self):
        """Create SecurityService for testing."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService()

    @pytest.mark.asyncio
    async def test_validate_request_empty_data(self, security_service):
        """Test validation with empty request data."""
        result = await security_service.validate_request_security({})
        
        assert result["is_safe"] is True
        assert result["security_score"] == 1.0

    @pytest.mark.asyncio
    async def test_check_content_safety_empty_content(self, security_service):
        """Test content safety with empty content."""
        result = await security_service.check_content_safety("")
        
        assert result["is_safe"] is True
        assert result["safety_score"] == 1.0
        assert result["filtered_content"] == ""

    def test_threat_detector_with_invalid_time(self):
        """Test threat detector behavior with time manipulation."""
        with patch('src.core.security_service.get_logger'):
            detector = ThreatDetector()
            
            # Test with negative time (edge case)
            with patch('time.time', return_value=-1000.0):
                threat = detector.detect_brute_force("192.168.1.1")
                # Should handle gracefully without crashing
                assert threat is None or isinstance(threat, SecurityThreat)


class TestSecurityServiceCOPPACompliance:
    """Test COPPA compliance aspects of SecurityService."""

    @pytest.fixture
    def security_service(self):
        """Create SecurityService for COPPA testing."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService()

    @pytest.mark.asyncio
    async def test_child_data_access_audit_logging(self, security_service):
        """Test that child data access is properly audited."""
        with patch('src.core.security_service.coppa_audit') as mock_audit:
            await security_service.validate_child_data_access(
                "child123", "child123", "read", {"user_type": "child"}
            )
            
            # Verify COPPA audit logging
            mock_audit.log_event.assert_called_once()
            audit_call = mock_audit.log_event.call_args[0][0]
            assert audit_call["event_type"] == "child_data_access"
            assert audit_call["child_id"] == "child123"
            assert audit_call["metadata"]["coppa_compliant"] is True

    @pytest.mark.asyncio
    async def test_content_safety_coppa_audit(self, security_service):
        """Test that content safety violations are audited for COPPA."""
        unsafe_content = "What's your home address?"
        
        with patch('src.core.security_service.coppa_audit') as mock_audit:
            await security_service.check_content_safety(unsafe_content, child_age=8)
            
            # Verify COPPA audit logging for safety violation
            mock_audit.log_event.assert_called_once()
            audit_call = mock_audit.log_event.call_args[0][0]
            assert audit_call["event_type"] == "content_safety_violation"
            assert audit_call["metadata"]["child_age"] == 8

    @pytest.mark.asyncio
    async def test_security_threat_coppa_audit(self, security_service):
        """Test that security threats are audited for COPPA compliance."""
        malicious_request = {
            "content": "<script>alert('XSS')</script>"
        }
        user_context = {
            "user_id": "user123",
            "ip_address": "192.168.1.1"
        }
        
        with patch('src.core.security_service.coppa_audit') as mock_audit:
            await security_service.validate_request_security(malicious_request, user_context)
            
            # Verify security threat is audited
            mock_audit.log_event.assert_called_once()
            audit_call = mock_audit.log_event.call_args[0][0]
            assert audit_call["event_type"] == "security_threat_detected"

    def test_child_id_privacy_protection(self):
        """Test that child IDs are properly protected in logs."""
        with patch('src.core.security_service.get_logger'):
            detector = ThreatDetector()
            
            child_id = "sensitive_child_id_12345"
            access_pattern = {"access_count": 100}
            
            threat = detector.detect_suspicious_child_access(
                "parent123", child_id, access_pattern
            )
            
            # Child ID should be hashed, not stored in plain text
            assert child_id not in str(threat.metadata)
            assert "child_id_hash" in threat.metadata
            assert len(threat.metadata["child_id_hash"]) == 16  # SHA256[:16]


class TestAccessPatternAnalysis:
    """Test access pattern analysis functionality."""

    @pytest.fixture
    def security_service(self):
        """Create SecurityService for testing."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService()

    @pytest.mark.asyncio
    async def test_access_log_creation(self, security_service):
        """Test that access logs are created properly."""
        user_context = {
            "user_type": "parent",
            "ip_address": "192.168.1.1"
        }
        
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=True):
            await security_service.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
            
            log_key = "parent123:child456:parent"
            assert log_key in security_service._access_logs
            assert len(security_service._access_logs[log_key]) == 1

    @pytest.mark.asyncio
    async def test_access_log_limit_enforcement(self, security_service):
        """Test that access logs are limited to 500 entries."""
        user_context = {
            "user_type": "parent",
            "ip_address": "192.168.1.1"
        }
        log_key = "parent123:child456:parent"
        
        # Pre-fill with 500 entries
        security_service._access_logs[log_key] = []
        for i in range(500):
            security_service._access_logs[log_key].append({
                "timestamp": datetime.utcnow() - timedelta(minutes=i),
                "access_type": "read",
                "ip_address": "192.168.1.1"
            })
        
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=True):
            await security_service.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
            
            # Should still be 500 (kept last 500)
            assert len(security_service._access_logs[log_key]) == 500

    @pytest.mark.asyncio
    async def test_access_thresholds_configuration(self, security_service):
        """Test access threshold configuration."""
        thresholds = security_service._access_thresholds
        
        assert thresholds["max_access_per_hour"] == 30
        assert thresholds["max_access_per_day"] == 200
        assert thresholds["max_frequency_per_minute"] == 10
        assert thresholds["unusual_hours"] == (0, 6)

    @pytest.mark.asyncio
    async def test_suspicious_pattern_multiple_indicators(self, security_service):
        """Test detection with all suspicious indicators."""
        user_context = {
            "user_type": "parent",
            "ip_address": "192.168.1.1"
        }
        log_key = "parent123:child456:parent"
        now = datetime.utcnow().replace(hour=2)  # Unusual hour
        
        # Pre-fill with excessive accesses
        security_service._access_logs[log_key] = []
        # Add entries for all time periods to trigger all thresholds
        for i in range(250):  # Exceed daily limit
            security_service._access_logs[log_key].append({
                "timestamp": now - timedelta(hours=i % 12),  # Within last day
                "access_type": "read",
                "ip_address": "192.168.1.1"
            })
        
        with patch.object(security_service, 'verify_parent_child_relationship', return_value=True), \
             patch('src.core.security_service.datetime') as mock_datetime, \
             patch('src.core.security_service.coppa_audit') as mock_audit, \
             patch('src.core.security_service.security_logger') as mock_logger:
            
            mock_datetime.utcnow.return_value = now
            
            result = await security_service.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
            
            # Should detect suspicious pattern and deny access
            assert result["access_allowed"] is False
            assert result["coppa_compliant"] is False
            
            # Should log suspicious activity
            suspicious_calls = [call for call in mock_audit.log_event.call_args_list 
                              if call[0][0].get("event_type") == "suspicious_activity"]
            assert len(suspicious_calls) >= 1


class TestSecurityServiceRateLimiting:
    """Test rate limiting integration in SecurityService."""

    @pytest.fixture
    def mock_rate_limiting_service(self):
        """Create mock rate limiting service."""
        return AsyncMock(spec=RateLimitingService)

    @pytest.fixture
    def security_service_with_rate_limiting(self, mock_rate_limiting_service):
        """Create SecurityService with rate limiting."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService(rate_limiting_service=mock_rate_limiting_service)

    @pytest.mark.asyncio
    async def test_validate_request_security_with_rate_limiting_allowed(self, security_service_with_rate_limiting):
        """Test security validation with rate limiting - request allowed."""
        request_data = {"content": "Hello world"}
        user_context = {"user_id": "child123", "child_age": 8}
        
        # Mock rate limiting service to allow request
        rate_limit_result = RateLimitResult(allowed=True, remaining=10)
        security_service_with_rate_limiting.rate_limiting_service.check_rate_limit.return_value = rate_limit_result
        
        result = await security_service_with_rate_limiting.validate_request_security(request_data, user_context)
        
        assert result["is_safe"] is True
        assert result["security_score"] == 1.0
        security_service_with_rate_limiting.rate_limiting_service.check_rate_limit.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_request_security_with_rate_limiting_blocked(self, security_service_with_rate_limiting):
        """Test security validation with rate limiting - request blocked."""
        request_data = {"content": "Hello world"}
        user_context = {"user_id": "child123", "child_age": 8}
        
        # Mock rate limiting service to block request
        rate_limit_result = RateLimitResult(
            allowed=False, 
            remaining=0, 
            reason="rate_limit_exceeded",
            retry_after_seconds=60
        )
        security_service_with_rate_limiting.rate_limiting_service.check_rate_limit.return_value = rate_limit_result
        
        with patch('src.core.security_service.security_logger') as mock_logger:
            result = await security_service_with_rate_limiting.validate_request_security(request_data, user_context)
            
            assert result["is_safe"] is False
            assert result["security_score"] == 0.0
            assert "rate_limit_exceeded" in result["recommendations"]
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_request_security_rate_limiting_error(self, security_service_with_rate_limiting):
        """Test security validation when rate limiting fails."""
        request_data = {"content": "Hello world"}
        user_context = {"user_id": "child123", "child_age": 8}
        
        # Mock rate limiting service to raise exception
        security_service_with_rate_limiting.rate_limiting_service.check_rate_limit.side_effect = Exception("Redis error")
        
        result = await security_service_with_rate_limiting.validate_request_security(request_data, user_context)
        
        # Should continue with other security checks despite rate limiting error
        assert result["is_safe"] is True  # No other threats in this case

    @pytest.mark.asyncio
    async def test_get_rate_limit_status_success(self, security_service_with_rate_limiting):
        """Test getting rate limit status successfully."""
        child_id = "child123"
        expected_stats = {
            "ai_request": {"current_requests": 5, "max_requests": 50, "remaining": 45},
            "conversation_message": {"current_requests": 10, "max_requests": 100, "remaining": 90}
        }
        
        security_service_with_rate_limiting.rate_limiting_service.get_usage_stats.return_value = expected_stats
        
        result = await security_service_with_rate_limiting.get_rate_limit_status(child_id)
        
        assert result == expected_stats
        security_service_with_rate_limiting.rate_limiting_service.get_usage_stats.assert_called_once_with(child_id)

    @pytest.mark.asyncio
    async def test_get_rate_limit_status_no_service(self):
        """Test getting rate limit status when service is not available."""
        with patch('src.core.security_service.get_logger'):
            security_service = SecurityService(rate_limiting_service=None)
            
            result = await security_service.get_rate_limit_status("child123")
            
            assert "error" in result
            assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_reset_rate_limits_success(self, security_service_with_rate_limiting):
        """Test resetting rate limits successfully."""
        child_id = "child123"
        operation = OperationType.AI_REQUEST
        
        result = await security_service_with_rate_limiting.reset_rate_limits(child_id, operation)
        
        assert result is True
        security_service_with_rate_limiting.rate_limiting_service.reset_limits.assert_called_once_with(child_id, operation)

    @pytest.mark.asyncio
    async def test_reset_rate_limits_error(self, security_service_with_rate_limiting):
        """Test resetting rate limits with error."""
        child_id = "child123"
        
        # Mock service to raise exception
        security_service_with_rate_limiting.rate_limiting_service.reset_limits.side_effect = Exception("Reset failed")
        
        result = await security_service_with_rate_limiting.reset_rate_limits(child_id)
        
        assert result is False


class TestSecurityServicePerformance:
    """Test performance scenarios and edge cases."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def security_service_with_redis(self, mock_redis):
        """Create SecurityService with mocked Redis."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_high_volume_brute_force_detection(self, security_service_with_redis):
        """Test brute force detection with high volume of requests."""
        ip_address = "192.168.1.100"
        
        # Mock Redis pipeline operations for high volume
        mock_pipeline = AsyncMock()
        mock_pipeline.execute.return_value = [None, None, 15]  # 15 attempts
        security_service_with_redis.redis.pipeline.return_value = mock_pipeline
        
        threat = await security_service_with_redis.threat_detector.detect_brute_force(ip_address, "user123")
        
        assert threat is not None
        assert threat.threat_type == "brute_force_attack"
        assert threat.severity == "high"

    @pytest.mark.asyncio
    async def test_redis_failure_fallback_brute_force(self, security_service_with_redis):
        """Test fallback to memory when Redis fails during brute force detection."""
        ip_address = "192.168.1.101"
        
        # Mock Redis to fail
        security_service_with_redis.redis.pipeline.side_effect = Exception("Redis connection lost")
        
        # Should fall back to in-memory tracking
        for _ in range(12):  # Exceed threshold
            threat = await security_service_with_redis.threat_detector.detect_brute_force(ip_address, "user123")
        
        assert threat is not None
        assert threat.threat_type == "brute_force_attack"

    @pytest.mark.asyncio
    async def test_large_dataset_access_pattern_analysis(self, security_service_with_redis):
        """Test access pattern analysis with large dataset."""
        user_context = {"user_type": "parent", "ip_address": "192.168.1.1"}
        
        # Mock Redis operations for optimized access pattern analysis
        mock_pipeline = AsyncMock()
        mock_pipeline.execute.return_value = [35, 250, 15]  # hour, day, minute counts
        security_service_with_redis.redis.pipeline.return_value = mock_pipeline
        
        with patch.object(security_service_with_redis, 'verify_parent_child_relationship', return_value=True), \
             patch('src.core.security_service.coppa_audit') as mock_audit, \
             patch('src.core.security_service.security_logger') as mock_logger:
            
            result = await security_service_with_redis.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
            
            # Should detect suspicious pattern efficiently
            assert result["access_allowed"] is False
            assert "suspicious_access_pattern_detected" in result["restrictions"]

    @pytest.mark.asyncio
    async def test_concurrent_security_validations(self, security_service_with_redis):
        """Test concurrent security validations for performance."""
        import asyncio
        
        # Mock Redis operations
        security_service_with_redis.redis.get.return_value = None  # Not blocked
        
        # Create multiple concurrent validation tasks
        tasks = []
        for i in range(100):
            request_data = {"content": f"Message {i}"}
            user_context = {"user_id": f"user{i}", "ip_address": f"192.168.1.{i}"}
            task = security_service_with_redis.validate_request_security(request_data, user_context)
            tasks.append(task)
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 100
        assert all(result["is_safe"] for result in results)

    @pytest.mark.asyncio
    async def test_memory_efficient_ip_blocking(self, security_service_with_redis):
        """Test memory-efficient IP blocking with Redis."""
        ip_addresses = [f"192.168.1.{i}" for i in range(1000)]
        
        # Mock Redis operations
        security_service_with_redis.redis.setex.return_value = True
        
        # Block many IPs
        for ip in ip_addresses:
            await security_service_with_redis.block_ip(ip, "automated_attack")
        
        # Verify Redis was used for persistence (not memory storage)
        assert len(security_service_with_redis.blocked_ips) == 0  # Should be empty (using Redis)
        assert security_service_with_redis.redis.setex.call_count == 1000

    @pytest.mark.asyncio
    async def test_redis_pipeline_optimization(self, security_service_with_redis):
        """Test Redis pipeline optimization for batch operations."""
        # Mock pipeline for efficient batch operations
        mock_pipeline = AsyncMock()
        mock_pipeline.execute.return_value = [10, 50, 5]  # Batch results
        security_service_with_redis.redis.pipeline.return_value = mock_pipeline
        
        # Test access pattern analysis (should use pipeline)
        user_context = {"user_type": "parent", "ip_address": "192.168.1.1"}
        
        with patch.object(security_service_with_redis, 'verify_parent_child_relationship', return_value=True):
            await security_service_with_redis.validate_child_data_access(
                "parent123", "child456", "read", user_context
            )
        
        # Verify pipeline was used for batch operations
        security_service_with_redis.redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_configurable_thresholds_application(self):
        """Test that configurable thresholds are properly applied."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.get_config') as mock_config:
            
            # Mock configuration with custom thresholds
            mock_config.return_value.SECURITY_BRUTE_FORCE_ATTEMPTS = 5
            mock_config.return_value.SECURITY_BRUTE_FORCE_WINDOW = 1800
            mock_config.return_value.SECURITY_ACCESS_MAX_PER_HOUR = 20
            
            detector = ThreatDetector()
            
            # Verify configuration is applied
            assert detector.config.SECURITY_BRUTE_FORCE_ATTEMPTS == 5
            assert detector.config.SECURITY_BRUTE_FORCE_WINDOW == 1800

    @pytest.mark.asyncio
    async def test_create_security_service_factory_with_rate_limiting(self):
        """Test security service factory creates integrated service."""
        with patch('src.core.security_service.get_config') as mock_config, \
             patch('src.core.security_service.aioredis') as mock_aioredis, \
             patch('src.infrastructure.rate_limiting.rate_limiter.create_rate_limiting_service') as mock_create_rl:
            
            mock_config.return_value.REDIS_URL = "redis://localhost:6379"
            mock_redis = AsyncMock()
            mock_aioredis.from_url.return_value = mock_redis
            mock_create_rl.return_value = AsyncMock(spec=RateLimitingService)
            
            service = await create_security_service()
            
            assert service.rate_limiting_service is not None
            assert service.redis is not None
            mock_create_rl.assert_called_once()

    def test_edge_case_empty_content_injection(self):
        """Test content injection detection with edge cases."""
        with patch('src.core.security_service.get_logger'):
            detector = ThreatDetector()
            
            # Test empty content
            threat = detector.detect_content_injection("", "user123")
            assert threat is None
            
            # Test whitespace only
            threat = detector.detect_content_injection("   \n\t  ", "user123")
            assert threat is None
            
            # Test single character patterns
            threat = detector.detect_content_injection("<", "user123")
            assert threat is None  # Not a complete pattern

    def test_edge_case_suspicious_child_access_boundary_values(self):
        """Test suspicious child access detection with boundary values."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.get_config') as mock_config:
            
            mock_config.return_value.SECURITY_CHILD_ACCESS_EXCESSIVE_COUNT = 50
            mock_config.return_value.SECURITY_CHILD_ACCESS_HIGH_FREQUENCY = 10
            
            detector = ThreatDetector()
            
            # Test exactly at threshold (should not trigger)
            access_pattern = {"access_count": 50, "access_frequency": 10, "unusual_hours": False}
            threat = detector.detect_suspicious_child_access("parent123", "child456", access_pattern)
            assert threat is None
            
            # Test just over threshold (should trigger)
            access_pattern = {"access_count": 51, "access_frequency": 11, "unusual_hours": False}
            threat = detector.detect_suspicious_child_access("parent123", "child456", access_pattern)
            assert threat is not None
            assert threat.severity == "critical"  # Multiple indicators


class TestMLAnomalyDetector:
    """Test ML-based anomaly detection capabilities."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def anomaly_detector(self, mock_redis):
        """Create MLAnomalyDetector instance for testing."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.get_config') as mock_config:
            
            mock_config.return_value = Mock()
            return MLAnomalyDetector(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_extract_behavior_features_normal_session(self, anomaly_detector):
        """Test behavior feature extraction from normal session."""
        user_id = "child123"
        session_data = {
            'session_duration': 1800,  # 30 minutes
            'requests': [
                {'content': 'Hello teddy bear!', 'endpoint': '/chat', 'error': False},
                {'content': 'Tell me a story', 'endpoint': '/chat', 'error': False},
                {'content': 'What is 2+2?', 'endpoint': '/chat', 'error': False}
            ],
            'safety_violations': 0,
            'age_inappropriate_attempts': 0
        }
        
        # Mock Redis operations
        anomaly_detector.redis.lrange.return_value = []
        
        features = await anomaly_detector.extract_behavior_features(user_id, session_data)
        
        assert features.user_id == user_id
        assert features.session_duration == 1800
        assert features.requests_per_minute == 0.1  # 3 requests in 30 minutes
        assert features.content_length_avg > 0
        assert features.unique_endpoints == 1
        assert features.error_rate == 0.0
        assert features.child_safety_violations == 0

    @pytest.mark.asyncio
    async def test_extract_behavior_features_empty_session(self, anomaly_detector):
        """Test behavior feature extraction from empty session."""
        user_id = "child456"
        session_data = {
            'session_duration': 0,
            'requests': [],
            'safety_violations': 0,
            'age_inappropriate_attempts': 0
        }
        
        features = await anomaly_detector.extract_behavior_features(user_id, session_data)
        
        assert features.user_id == user_id
        assert features.session_duration == 0
        assert features.requests_per_minute == 0
        assert features.content_length_avg == 0
        assert features.unique_endpoints == 0
        assert features.error_rate == 0

    @pytest.mark.asyncio
    async def test_detect_temporal_anomalies_unusual_hours(self, anomaly_detector):
        """Test detection of temporal anomalies during unusual hours."""
        # Create features for very late hour access
        features = BehaviorFeatures(
            user_id="child123",
            timestamp=datetime.utcnow(),
            hour_of_day=2,  # 2 AM - unusual for children
            day_of_week=1,
            session_duration=3600,
            requests_per_minute=1.0,
            content_length_avg=50,
            content_length_std=10,
            unique_endpoints=2,
            error_rate=0.0,
            child_safety_violations=0,
            age_inappropriate_attempts=0
        )
        
        score = await anomaly_detector._detect_temporal_anomalies(features)
        
        assert score > 0.5  # Should detect unusual hour
        
    @pytest.mark.asyncio
    async def test_detect_activity_anomalies_high_frequency(self, anomaly_detector):
        """Test detection of activity anomalies with high request frequency."""
        features = BehaviorFeatures(
            user_id="child123",
            timestamp=datetime.utcnow(),
            hour_of_day=10,
            day_of_week=1,
            session_duration=300,
            requests_per_minute=20.0,  # Very high frequency
            content_length_avg=50,
            content_length_std=10,
            unique_endpoints=5,
            error_rate=0.0,
            child_safety_violations=0,
            age_inappropriate_attempts=0
        )
        
        score = await anomaly_detector._detect_activity_anomalies(features)
        
        assert score > 0.4  # Should detect high activity

    @pytest.mark.asyncio
    async def test_detect_child_safety_anomalies_violations(self, anomaly_detector):
        """Test detection of child safety anomalies."""
        features = BehaviorFeatures(
            user_id="child123",
            timestamp=datetime.utcnow(),
            hour_of_day=10,
            day_of_week=1,
            session_duration=1800,
            requests_per_minute=2.0,
            content_length_avg=50,
            content_length_std=10,
            unique_endpoints=2,
            error_rate=0.0,
            child_safety_violations=3,  # Multiple safety violations
            age_inappropriate_attempts=2
        )
        
        score = await anomaly_detector._detect_child_safety_anomalies(features)
        
        assert score > 0.8  # Should be very high for safety violations

    @pytest.mark.asyncio
    async def test_detect_behavioral_anomalies_normal_behavior(self, anomaly_detector):
        """Test behavioral anomaly detection with normal behavior."""
        features = BehaviorFeatures(
            user_id="child123",
            timestamp=datetime.utcnow(),
            hour_of_day=14,  # 2 PM - normal hour
            day_of_week=1,
            session_duration=1800,  # 30 minutes - normal
            requests_per_minute=2.0,  # Normal frequency
            content_length_avg=30,  # Normal content length
            content_length_std=5,
            unique_endpoints=2,
            error_rate=0.0,
            child_safety_violations=0,
            age_inappropriate_attempts=0
        )
        
        result = await anomaly_detector.detect_behavioral_anomalies(features)
        
        assert not result.is_anomaly
        assert result.anomaly_score < 0.6
        assert len(result.detected_patterns) == 0
        assert "Normal behavior detected" in result.explanation

    @pytest.mark.asyncio
    async def test_detect_behavioral_anomalies_multiple_patterns(self, anomaly_detector):
        """Test behavioral anomaly detection with multiple suspicious patterns."""
        features = BehaviorFeatures(
            user_id="child123",
            timestamp=datetime.utcnow(),
            hour_of_day=1,  # 1 AM - unusual
            day_of_week=1,
            session_duration=7200,  # 2 hours - very long
            requests_per_minute=25.0,  # Very high frequency
            content_length_avg=200,  # Long content
            content_length_std=50,
            unique_endpoints=10,
            error_rate=0.2,  # High error rate
            child_safety_violations=2,  # Safety violations
            age_inappropriate_attempts=1
        )
        
        result = await anomaly_detector.detect_behavioral_anomalies(features)
        
        assert result.is_anomaly
        assert result.anomaly_score > 0.8
        assert len(result.detected_patterns) >= 2
        assert 'child_safety_anomaly' in result.detected_patterns
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_update_user_baseline_redis(self, anomaly_detector):
        """Test updating user baseline with Redis storage."""
        features = BehaviorFeatures(
            user_id="child123",
            timestamp=datetime.utcnow(),
            hour_of_day=10,
            day_of_week=1,
            session_duration=1800,
            requests_per_minute=2.0,
            content_length_avg=50,
            content_length_std=10,
            unique_endpoints=2,
            error_rate=0.0,
            child_safety_violations=0,
            age_inappropriate_attempts=0
        )
        
        await anomaly_detector._update_user_baseline(features)
        
        # Verify Redis operations
        anomaly_detector.redis.lpush.assert_called_once()
        anomaly_detector.redis.ltrim.assert_called_once()
        anomaly_detector.redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_historical_data_redis(self, anomaly_detector):
        """Test retrieving user historical data from Redis."""
        user_id = "child123"
        
        # Mock Redis response
        mock_sessions = [
            json.dumps({
                'timestamp': (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                'hour_of_day': 10,
                'session_duration': 1800
            }),
            json.dumps({
                'timestamp': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'hour_of_day': 9,
                'session_duration': 1200
            })
        ]
        anomaly_detector.redis.lrange.return_value = mock_sessions
        
        historical_data = await anomaly_detector._get_user_historical_data(user_id, 24)
        
        assert len(historical_data) == 2
        anomaly_detector.redis.lrange.assert_called_once_with(f"user_history:{user_id}", 0, -1)

    def test_calculate_confidence_high_consistency(self, anomaly_detector):
        """Test confidence calculation with high consistency."""
        scores = [0.8, 0.7, 0.9, 0.6]  # Mostly high scores
        patterns = ['temporal_anomaly', 'activity_anomaly']
        
        confidence = anomaly_detector._calculate_confidence(scores, patterns)
        
        assert confidence >= 0.5  # Should have reasonable confidence

    def test_calculate_confidence_with_safety_boost(self, anomaly_detector):
        """Test confidence calculation with child safety boost."""
        scores = [0.6, 0.4, 0.3]
        patterns = ['child_safety_anomaly']  # Safety pattern gets boost
        
        confidence = anomaly_detector._calculate_confidence(scores, patterns)
        
        assert confidence >= 0.3  # Should get safety boost

    def test_generate_explanation_no_anomaly(self, anomaly_detector):
        """Test explanation generation for normal behavior."""
        patterns = []
        risk_factors = []
        score = 0.2
        
        explanation = anomaly_detector._generate_explanation(patterns, risk_factors, score)
        
        assert "Normal behavior detected" in explanation

    def test_generate_explanation_with_safety_concern(self, anomaly_detector):
        """Test explanation generation with child safety concerns."""
        patterns = ['child_safety_anomaly', 'temporal_anomaly']
        risk_factors = ['Child safety violations detected', 'Unusual access time patterns']
        score = 0.9
        
        explanation = anomaly_detector._generate_explanation(patterns, risk_factors, score)
        
        assert "Anomaly detected" in explanation
        assert "⚠️ Child safety concerns identified" in explanation
        assert "Risk factors:" in explanation


class TestThreatDetectorWithAnomalyDetection:
    """Test ThreatDetector integration with ML anomaly detection."""

    @pytest.fixture
    def threat_detector_with_ml(self):
        """Create ThreatDetector with ML anomaly detection."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.get_config'):
            return ThreatDetector()

    @pytest.mark.asyncio
    async def test_detect_behavioral_anomalies_integration(self, threat_detector_with_ml):
        """Test behavioral anomaly detection integration."""
        user_id = "child123"
        session_data = {
            'session_duration': 1800,
            'requests': [
                {'content': 'Hello', 'endpoint': '/chat', 'error': False}
            ],
            'safety_violations': 2,  # Safety violations present
            'age_inappropriate_attempts': 1
        }
        user_context = {"ip_address": "192.168.1.100"}
        
        # Mock the ML anomaly detector to return an anomaly
        mock_anomaly_result = AnomalyResult(
            is_anomaly=True,
            anomaly_score=0.9,
            confidence=0.8,
            detected_patterns=['child_safety_anomaly'],
            risk_factors=['Child safety violations detected'],
            explanation="High risk behavior detected",
            threshold_used=0.6
        )
        
        with patch.object(
            threat_detector_with_ml.ml_anomaly_detector,
            'detect_behavioral_anomalies',
            return_value=mock_anomaly_result
        ):
            threat = await threat_detector_with_ml.detect_behavioral_anomalies(
                user_id, session_data, user_context
            )
            
            assert threat is not None
            assert threat.threat_type == "behavioral_anomaly"
            assert threat.severity == "critical"  # Child safety = critical
            assert threat.user_id == user_id
            assert threat.metadata["anomaly_score"] == 0.9
            assert "child_safety_anomaly" in threat.metadata["detected_patterns"]

    @pytest.mark.asyncio
    async def test_detect_behavioral_anomalies_no_anomaly(self, threat_detector_with_ml):
        """Test behavioral anomaly detection when no anomaly is detected."""
        user_id = "child456"
        session_data = {
            'session_duration': 1800,
            'requests': [{'content': 'Hello', 'endpoint': '/chat', 'error': False}],
            'safety_violations': 0,
            'age_inappropriate_attempts': 0
        }
        
        # Mock the ML anomaly detector to return no anomaly
        mock_anomaly_result = AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.3,
            confidence=0.9,
            detected_patterns=[],
            risk_factors=[],
            explanation="Normal behavior detected",
            threshold_used=0.6
        )
        
        with patch.object(
            threat_detector_with_ml.ml_anomaly_detector,
            'detect_behavioral_anomalies',
            return_value=mock_anomaly_result
        ):
            threat = await threat_detector_with_ml.detect_behavioral_anomalies(
                user_id, session_data
            )
            
            assert threat is None


class TestSecurityServiceBehavioralAnalysis:
    """Test SecurityService behavioral analysis integration."""

    @pytest.fixture
    def security_service_with_ml(self):
        """Create SecurityService with ML capabilities."""
        with patch('src.core.security_service.get_logger'), \
             patch('src.core.security_service.security_logger'), \
             patch('src.core.security_service.coppa_audit'):
            return SecurityService()

    @pytest.mark.asyncio
    async def test_validate_request_security_with_behavioral_anomaly(self, security_service_with_ml):
        """Test request validation with behavioral anomaly detection."""
        request_data = {"content": "Hello world"}
        user_context = {
            "user_id": "child123",
            "session_duration": 7200,  # Very long session
            "safety_violations": 1,
            "ip_address": "192.168.1.100"
        }
        
        # Mock behavioral anomaly detection
        mock_threat = SecurityThreat(
            threat_id="behavioral_anomaly_123",
            threat_type="behavioral_anomaly",
            severity="high",
            description="Suspicious behavior detected",
            detected_at=datetime.utcnow(),
            user_id="child123",
            metadata={"anomaly_score": 0.8}
        )
        
        with patch.object(
            security_service_with_ml.threat_detector,
            'detect_behavioral_anomalies',
            return_value=mock_threat
        ), patch('src.core.security_service.security_logger') as mock_logger:
            
            result = await security_service_with_ml.validate_request_security(request_data, user_context)
            
            assert result["is_safe"] is False
            assert result["security_score"] < 1.0
            assert len(result["threats_detected"]) == 1
            assert result["threats_detected"][0].threat_type == "behavioral_anomaly"
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_user_behavior_comprehensive(self, security_service_with_ml):
        """Test comprehensive user behavior analysis."""
        user_id = "child123"
        session_data = {
            'session_duration': 1800,
            'requests': [
                {'content': 'Hello teddy!', 'endpoint': '/chat', 'error': False},
                {'content': 'Tell me a story', 'endpoint': '/stories', 'error': False}
            ],
            'safety_violations': 0,
            'age_inappropriate_attempts': 0
        }
        
        # Mock feature extraction and anomaly detection
        mock_features = BehaviorFeatures(
            user_id=user_id,
            timestamp=datetime.utcnow(),
            hour_of_day=14,
            day_of_week=1,
            session_duration=1800,
            requests_per_minute=2.0,
            content_length_avg=25,
            content_length_std=5,
            unique_endpoints=2,
            error_rate=0.0,
            child_safety_violations=0,
            age_inappropriate_attempts=0
        )
        
        mock_anomaly_result = AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.2,
            confidence=0.9,
            detected_patterns=[],
            risk_factors=[],
            explanation="Normal behavior detected",
            threshold_used=0.6
        )
        
        with patch.object(
            security_service_with_ml.threat_detector.ml_anomaly_detector,
            'extract_behavior_features',
            return_value=mock_features
        ), patch.object(
            security_service_with_ml.threat_detector.ml_anomaly_detector,
            'detect_behavioral_anomalies',
            return_value=mock_anomaly_result
        ):
            
            analysis = await security_service_with_ml.analyze_user_behavior(user_id, session_data)
            
            assert analysis["user_id"] == user_id
            assert "behavior_summary" in analysis
            assert "anomaly_detection" in analysis
            assert analysis["behavior_summary"]["session_duration"] == 1800
            assert analysis["anomaly_detection"]["is_anomaly"] is False
            assert analysis["anomaly_detection"]["anomaly_score"] == 0.2

    @pytest.mark.asyncio
    async def test_analyze_user_behavior_with_recommendations(self, security_service_with_ml):
        """Test user behavior analysis with recommendations for anomalies."""
        user_id = "child456"
        session_data = {
            'session_duration': 7200,
            'requests': [],
            'safety_violations': 2,
            'age_inappropriate_attempts': 1
        }
        
        # Mock anomalous behavior
        mock_features = BehaviorFeatures(
            user_id=user_id,
            timestamp=datetime.utcnow(),
            hour_of_day=2,  # Unusual hour
            day_of_week=1,
            session_duration=7200,
            requests_per_minute=0,
            content_length_avg=0,
            content_length_std=0,
            unique_endpoints=0,
            error_rate=0,
            child_safety_violations=2,
            age_inappropriate_attempts=1
        )
        
        mock_anomaly_result = AnomalyResult(
            is_anomaly=True,
            anomaly_score=0.9,
            confidence=0.8,
            detected_patterns=['temporal_anomaly', 'child_safety_anomaly'],
            risk_factors=['Unusual access time', 'Child safety violations'],
            explanation="Multiple anomalies detected",
            threshold_used=0.6
        )
        
        with patch.object(
            security_service_with_ml.threat_detector.ml_anomaly_detector,
            'extract_behavior_features',
            return_value=mock_features
        ), patch.object(
            security_service_with_ml.threat_detector.ml_anomaly_detector,
            'detect_behavioral_anomalies',
            return_value=mock_anomaly_result
        ):
            
            analysis = await security_service_with_ml.analyze_user_behavior(user_id, session_data)
            
            assert "recommendations" in analysis
            recommendations = analysis["recommendations"]
            assert any("unusual access times" in rec.lower() for rec in recommendations)
            assert any("child safety" in rec.lower() for rec in recommendations)
            assert any("urgent" in rec.lower() for rec in recommendations)