"""
Comprehensive unit tests for data_encryption_service module.
Production-grade security testing for data encryption, audit logging, and COPPA compliance.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.infrastructure.security.data_encryption_service import (
    DataEncryptionService,
    EncryptionLevel,
    AuditEventType,
    DataClassification,
    AuditLogEntry,
    EncryptionKeyInfo,
    create_data_encryption_service
)


class TestEncryptionLevel:
    """Test EncryptionLevel enum."""

    def test_encryption_levels(self):
        """Test all encryption levels are defined."""
        assert EncryptionLevel.NONE == "none"
        assert EncryptionLevel.STANDARD == "standard"
        assert EncryptionLevel.SENSITIVE == "sensitive"
        assert EncryptionLevel.HIGHLY_SENSITIVE == "highly_sensitive"


class TestAuditEventType:
    """Test AuditEventType enum."""

    def test_audit_event_types(self):
        """Test all audit event types are defined."""
        expected_types = [
            "data_access", "data_create", "data_update", "data_delete",
            "key_rotation", "unauthorized_access", "data_export",
            "coppa_violation", "security_incident", "login_attempt",
            "permission_change"
        ]
        
        for event_type in expected_types:
            assert event_type in [e.value for e in AuditEventType]


class TestDataClassification:
    """Test DataClassification enum."""

    def test_data_classifications(self):
        """Test all data classifications are defined."""
        assert DataClassification.PUBLIC == "public"
        assert DataClassification.INTERNAL == "internal"
        assert DataClassification.CONFIDENTIAL == "confidential"
        assert DataClassification.RESTRICTED == "restricted"


class TestAuditLogEntry:
    """Test AuditLogEntry dataclass."""

    def test_audit_log_entry_creation(self):
        """Test AuditLogEntry creation with required fields."""
        entry = AuditLogEntry(
            event_id="test-123",
            event_type=AuditEventType.DATA_ACCESS,
            timestamp=datetime.utcnow(),
            user_id="user-456",
            user_type="parent",
            child_id="child-789",
            action_performed="accessed child data",
            resource_type="child",
            resource_id="child-789",
            data_classification=DataClassification.RESTRICTED,
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            success=True
        )
        
        assert entry.event_id == "test-123"
        assert entry.event_type == AuditEventType.DATA_ACCESS
        assert entry.user_id == "user-456"
        assert entry.child_id == "child-789"
        assert entry.success is True

    def test_audit_log_entry_to_dict(self):
        """Test AuditLogEntry to_dict conversion."""
        timestamp = datetime.utcnow()
        entry = AuditLogEntry(
            event_id="test-123",
            event_type=AuditEventType.DATA_CREATE,
            timestamp=timestamp,
            user_id="user-456",
            user_type="admin",
            child_id=None,
            action_performed="created user account",
            resource_type="user",
            resource_id="user-456",
            data_classification=DataClassification.CONFIDENTIAL,
            ip_address="10.0.0.1",
            user_agent="AdminPanel/2.0",
            success=True,
            metadata={"source": "admin_panel"}
        )
        
        result = entry.to_dict()
        
        assert isinstance(result, dict)
        assert result["event_id"] == "test-123"
        assert result["timestamp"] == timestamp.isoformat()
        assert result["metadata"] == {"source": "admin_panel"}


class TestDataEncryptionService:
    """Test DataEncryptionService main functionality."""

    @pytest.fixture
    async def encryption_service(self):
        """Create DataEncryptionService for testing."""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = AsyncMock(spec=True)
            mock_redis.from_url.return_value = mock_redis_instance
            
            service = DataEncryptionService(
                redis_url="redis://localhost:6379/0",
                audit_retention_days=365,
                key_rotation_days=90
            )
            service.redis = mock_redis_instance
            
            yield service
            
            await service.close()

    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "email": "test@example.com",
            "phone_number": "+1234567890",
            "child_name": "Alice",
            "child_age": 8,
            "session_metadata": {"device": "mobile"}
        }

    def test_initialization(self, encryption_service):
        """Test service initialization."""
        assert encryption_service.master_key is not None
        assert encryption_service.fernet is not None
        assert encryption_service.private_key is not None
        assert encryption_service.public_key is not None
        assert encryption_service.key_info is not None
        assert encryption_service.field_encryption_map is not None

    def test_field_encryption_mappings(self, encryption_service):
        """Test field encryption level mappings."""
        mappings = encryption_service.field_encryption_map
        
        # Test sensitive fields
        assert mappings["email"] == EncryptionLevel.SENSITIVE
        assert mappings["child_name"] == EncryptionLevel.SENSITIVE
        assert mappings["conversation_content"] == EncryptionLevel.SENSITIVE
        
        # Test highly sensitive fields
        assert mappings["ssn"] == EncryptionLevel.HIGHLY_SENSITIVE
        assert mappings["child_location"] == EncryptionLevel.HIGHLY_SENSITIVE
        assert mappings["voice_recordings"] == EncryptionLevel.HIGHLY_SENSITIVE
        
        # Test standard fields
        assert mappings["device_info"] == EncryptionLevel.STANDARD

    @pytest.mark.asyncio
    async def test_encrypt_field_none_level(self, encryption_service):
        """Test field encryption with NONE level."""
        result = await encryption_service.encrypt_field(
            "test_field", "test_value", EncryptionLevel.NONE
        )
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_encrypt_field_standard_level(self, encryption_service):
        """Test field encryption with STANDARD level."""
        test_value = "test_standard_value"
        encrypted = await encryption_service.encrypt_field(
            "test_field", test_value, EncryptionLevel.STANDARD
        )
        
        assert encrypted != test_value
        assert isinstance(encrypted, str)
        
        # Test decryption
        decrypted = await encryption_service.decrypt_field(
            "test_field", encrypted, EncryptionLevel.STANDARD
        )
        assert decrypted == test_value

    @pytest.mark.asyncio
    async def test_encrypt_field_sensitive_level(self, encryption_service):
        """Test field encryption with SENSITIVE level."""
        test_value = "sensitive_data_value"
        encrypted = await encryption_service.encrypt_field(
            "email", test_value  # email maps to SENSITIVE
        )
        
        assert encrypted != test_value
        assert isinstance(encrypted, str)
        
        # Test decryption
        decrypted = await encryption_service.decrypt_field("email", encrypted)
        assert decrypted == test_value

    @pytest.mark.asyncio
    async def test_encrypt_field_highly_sensitive_level(self, encryption_service):
        """Test field encryption with HIGHLY_SENSITIVE level."""
        test_value = "highly_sensitive_data"
        encrypted = await encryption_service.encrypt_field(
            "ssn", test_value  # ssn maps to HIGHLY_SENSITIVE
        )
        
        assert encrypted != test_value
        assert isinstance(encrypted, str)
        
        # Test decryption
        decrypted = await encryption_service.decrypt_field("ssn", encrypted)
        assert decrypted == test_value

    @pytest.mark.asyncio
    async def test_encrypt_field_with_none_value(self, encryption_service):
        """Test field encryption with None value."""
        result = await encryption_service.encrypt_field("test_field", None)
        assert result is None
        
        # Test decryption of None
        decrypted = await encryption_service.decrypt_field("test_field", None)
        assert decrypted is None

    @pytest.mark.asyncio
    async def test_encrypt_field_with_complex_data(self, encryption_service):
        """Test field encryption with complex data types."""
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "number": 42
        }
        
        encrypted = await encryption_service.encrypt_field(
            "complex_field", complex_data
        )
        
        assert encrypted != str(complex_data)
        
        # Test decryption - should return JSON string
        decrypted = await encryption_service.decrypt_field("complex_field", encrypted)
        assert json.loads(decrypted) == complex_data

    @pytest.mark.asyncio
    async def test_encrypt_user_data(self, encryption_service, sample_user_data):
        """Test encrypting complete user data."""
        encrypted_data = await encryption_service.encrypt_user_data(sample_user_data)
        
        # Check all fields are present
        assert set(encrypted_data.keys()) == set(sample_user_data.keys())
        
        # Check sensitive fields are encrypted
        assert encrypted_data["email"] != sample_user_data["email"]
        assert encrypted_data["child_name"] != sample_user_data["child_name"]
        
        # Test decryption
        decrypted_data = await encryption_service.decrypt_user_data(encrypted_data)
        assert decrypted_data["email"] == sample_user_data["email"]
        assert decrypted_data["child_name"] == sample_user_data["child_name"]

    @pytest.mark.asyncio
    async def test_encryption_decryption_consistency(self, encryption_service):
        """Test encryption/decryption consistency across all levels."""
        test_cases = [
            ("public_field", "public_data", EncryptionLevel.NONE),
            ("standard_field", "standard_data", EncryptionLevel.STANDARD),
            ("sensitive_field", "sensitive_data", EncryptionLevel.SENSITIVE),
            ("highly_sensitive_field", "highly_sensitive_data", EncryptionLevel.HIGHLY_SENSITIVE),
        ]
        
        for field_name, test_value, encryption_level in test_cases:
            encrypted = await encryption_service.encrypt_field(
                field_name, test_value, encryption_level
            )
            decrypted = await encryption_service.decrypt_field(
                field_name, encrypted, encryption_level
            )
            assert decrypted == test_value, f"Failed for level {encryption_level}"

    @pytest.mark.asyncio
    async def test_encryption_error_handling(self, encryption_service):
        """Test encryption error handling."""
        with patch.object(encryption_service, 'fernet') as mock_fernet:
            mock_fernet.encrypt.side_effect = Exception("Encryption failed")
            
            # Should log security event and raise exception
            with pytest.raises(Exception, match="Encryption failed"):
                await encryption_service.encrypt_field("test_field", "test_value")

    @pytest.mark.asyncio
    async def test_decryption_error_handling(self, encryption_service):
        """Test decryption error handling."""
        with patch.object(encryption_service, 'fernet') as mock_fernet:
            mock_fernet.decrypt.side_effect = Exception("Decryption failed")
            
            # Should log security event and raise exception
            with pytest.raises(Exception, match="Decryption failed"):
                await encryption_service.decrypt_field("test_field", "encrypted_value")


class TestAuditLogging:
    """Test audit logging functionality."""

    @pytest.fixture
    async def encryption_service(self):
        """Create DataEncryptionService for audit testing."""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = AsyncMock(spec=True)
            mock_redis.from_url.return_value = mock_redis_instance
            
            service = DataEncryptionService(
                redis_url="redis://localhost:6379/0",
                audit_retention_days=365,
                key_rotation_days=90
            )
            service.redis = mock_redis_instance
            
            yield service
            
            await service.close()

    @pytest.mark.asyncio
    async def test_log_audit_event_basic(self, encryption_service):
        """Test basic audit event logging."""
        await encryption_service.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            action_performed="accessed user profile",
            resource_type="user",
            user_id="user-123",
            resource_id="profile-456",
            success=True
        )
        
        # Check that event was added to buffer
        assert len(encryption_service._audit_buffer) == 1
        entry = encryption_service._audit_buffer[0]
        assert entry.event_type == AuditEventType.DATA_ACCESS
        assert entry.user_id == "user-123"
        assert entry.success is True

    @pytest.mark.asyncio
    async def test_log_audit_event_with_all_fields(self, encryption_service):
        """Test audit event logging with all fields."""
        metadata = {"source": "web_app", "session_id": "session-789"}
        data_before = {"field": "old_value"}
        data_after = {"field": "new_value"}
        
        await encryption_service.log_audit_event(
            event_type=AuditEventType.DATA_UPDATE,
            action_performed="updated user profile",
            resource_type="user",
            user_id="user-123",
            user_type="parent",
            child_id="child-456",
            resource_id="profile-789",
            data_classification=DataClassification.RESTRICTED,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            success=True,
            error_message=None,
            data_before=data_before,
            data_after=data_after,
            metadata=metadata
        )
        
        entry = encryption_service._audit_buffer[0]
        assert entry.child_id == "child-456"
        assert entry.data_classification == DataClassification.RESTRICTED
        assert entry.metadata == metadata
        assert entry.data_before == data_before
        assert entry.data_after == data_after

    @pytest.mark.asyncio
    async def test_audit_buffer_flush_on_size_limit(self, encryption_service):
        """Test audit buffer flushes when size limit is reached."""
        # Set small buffer size for testing
        encryption_service.max_audit_batch_size = 3
        
        # Add events to fill buffer
        for i in range(3):
            await encryption_service.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                action_performed=f"access {i}",
                resource_type="test",
                user_id=f"user-{i}"
            )
        
        # Buffer should have been flushed
        assert len(encryption_service._audit_buffer) == 0
        
        # Redis operations should have been called
        encryption_service.redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_critical_event_immediate_flush(self, encryption_service):
        """Test critical events trigger immediate flush."""
        critical_events = [
            AuditEventType.UNAUTHORIZED_ACCESS,
            AuditEventType.COPPA_VIOLATION,
            AuditEventType.SECURITY_INCIDENT
        ]
        
        for event_type in critical_events:
            await encryption_service.log_audit_event(
                event_type=event_type,
                action_performed="critical event",
                resource_type="security",
                user_id="user-123"
            )
            
        # Should have called flush multiple times for critical events
        assert encryption_service.redis.pipeline.call_count >= len(critical_events)

    @pytest.mark.asyncio
    async def test_get_audit_logs_by_user(self, encryption_service):
        """Test retrieving audit logs by user ID."""
        # Mock Redis response
        mock_entries = [
            json.dumps({
                "event_id": "event-1",
                "event_type": "data_access",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "user-123",
                "user_type": "parent",
                "child_id": None,
                "action_performed": "accessed profile",
                "resource_type": "user",
                "resource_id": "profile-123",
                "data_classification": "internal",
                "ip_address": "192.168.1.1",
                "user_agent": "TestAgent",
                "success": True
            })
        ]
        
        encryption_service.redis.zrevrangebyscore.return_value = mock_entries
        
        logs = await encryption_service.get_audit_logs(user_id="user-123", limit=10)
        
        assert len(logs) == 1
        assert logs[0].user_id == "user-123"
        assert logs[0].event_type == AuditEventType.DATA_ACCESS

    @pytest.mark.asyncio
    async def test_get_audit_logs_by_child(self, encryption_service):
        """Test retrieving audit logs by child ID."""
        mock_entries = [
            json.dumps({
                "event_id": "event-1",
                "event_type": "data_access",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "parent-123",
                "user_type": "parent",
                "child_id": "child-456",
                "action_performed": "accessed child data",
                "resource_type": "child",
                "resource_id": "child-456",
                "data_classification": "restricted",
                "ip_address": "192.168.1.1",
                "user_agent": "TestAgent",
                "success": True
            })
        ]
        
        encryption_service.redis.zrevrangebyscore.return_value = mock_entries
        
        logs = await encryption_service.get_audit_logs(child_id="child-456")
        
        assert len(logs) == 1
        assert logs[0].child_id == "child-456"
        assert logs[0].data_classification == DataClassification.RESTRICTED

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_time_range(self, encryption_service):
        """Test retrieving audit logs with time range."""
        start_time = datetime.utcnow() - timedelta(hours=24)
        end_time = datetime.utcnow()
        
        encryption_service.redis.zrevrangebyscore.return_value = []
        
        logs = await encryption_service.get_audit_logs(
            start_time=start_time,
            end_time=end_time
        )
        
        # Verify Redis was called with correct time range
        encryption_service.redis.zrevrangebyscore.assert_called_once()
        call_args = encryption_service.redis.zrevrangebyscore.call_args
        assert call_args[0][1] == end_time.timestamp()  # max_score
        assert call_args[0][2] == start_time.timestamp()  # min_score

    @pytest.mark.asyncio
    async def test_audit_log_parsing_error_handling(self, encryption_service):
        """Test handling of malformed audit log entries."""
        # Mock Redis response with invalid JSON
        invalid_entries = ['invalid_json', '{"incomplete": "entry"}']
        encryption_service.redis.zrevrangebyscore.return_value = invalid_entries
        
        logs = await encryption_service.get_audit_logs(user_id="user-123")
        
        # Should return empty list for invalid entries
        assert logs == []


class TestSecurityMonitoring:
    """Test security monitoring functionality."""

    @pytest.fixture
    async def encryption_service(self):
        """Create DataEncryptionService for security testing."""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = AsyncMock(spec=True)
            mock_redis.from_url.return_value = mock_redis_instance
            
            service = DataEncryptionService(redis_url="redis://localhost:6379/0")
            service.redis = mock_redis_instance
            
            yield service
            
            await service.close()

    @pytest.mark.asyncio
    async def test_log_security_event(self, encryption_service):
        """Test security event logging."""
        await encryption_service._log_security_event(
            "unauthorized_access_attempt",
            {"ip": "192.168.1.100", "user_agent": "BadBot/1.0"}
        )
        
        # Check event was added to memory
        assert len(encryption_service._security_events) == 1
        event = encryption_service._security_events[0]
        assert event["event_type"] == "unauthorized_access_attempt"
        assert event["details"]["ip"] == "192.168.1.100"
        
        # Check Redis operations
        encryption_service.redis.lpush.assert_called_once()
        encryption_service.redis.ltrim.assert_called_once()
        encryption_service.redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_security_events_memory_limit(self, encryption_service):
        """Test security events memory limit enforcement."""
        # Add many events to trigger cleanup
        for i in range(1200):  # More than 1000 limit
            await encryption_service._log_security_event(f"event_{i}", {})
        
        # Should keep only last 500 events
        assert len(encryption_service._security_events) == 500

    @pytest.mark.asyncio
    async def test_alert_security_incident(self, encryption_service):
        """Test security incident alerting."""
        audit_entry = AuditLogEntry(
            event_id="incident-123",
            event_type=AuditEventType.SECURITY_INCIDENT,
            timestamp=datetime.utcnow(),
            user_id="attacker-456",
            user_type="unknown",
            child_id="child-789",
            action_performed="attempted unauthorized access",
            resource_type="child_data",
            resource_id="child-789",
            data_classification=DataClassification.RESTRICTED,
            ip_address="10.0.0.100",
            user_agent="AttackBot/1.0",
            success=False
        )
        
        await encryption_service._alert_security_incident(audit_entry)
        
        # Check incident was stored in Redis
        encryption_service.redis.lpush.assert_called()
        call_args = encryption_service.redis.lpush.call_args[0]
        assert call_args[0] == "security_incidents"
        
        incident_data = json.loads(call_args[1])
        assert incident_data["audit_event_id"] == "incident-123"
        assert incident_data["severity"] == "HIGH"

    @pytest.mark.asyncio
    async def test_detect_anomalous_activity_high_volume(self, encryption_service):
        """Test detection of high activity volume."""
        # Mock high volume of recent logs
        mock_logs = []
        for i in range(150):  # Above threshold of 100
            mock_logs.append(AuditLogEntry(
                event_id=f"event-{i}",
                event_type=AuditEventType.DATA_ACCESS,
                timestamp=datetime.utcnow(),
                user_id="user-123",
                user_type="parent",
                child_id=None,
                action_performed=f"action {i}",
                resource_type="user",
                resource_id="user-123",
                data_classification=DataClassification.INTERNAL,
                ip_address="192.168.1.1",
                user_agent="TestAgent",
                success=True
            ))
        
        with patch.object(encryption_service, 'get_audit_logs', return_value=mock_logs):
            anomalies = await encryption_service.detect_anomalous_activity("user-123")
        
        # Should detect high activity volume
        high_volume_anomaly = next(
            (a for a in anomalies if a["type"] == "high_activity_volume"), None
        )
        assert high_volume_anomaly is not None
        assert high_volume_anomaly["count"] == 150
        assert high_volume_anomaly["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_detect_anomalous_activity_failed_attempts(self, encryption_service):
        """Test detection of multiple failed attempts."""
        # Mock failed attempts
        mock_logs = []
        for i in range(15):  # Above threshold of 10
            mock_logs.append(AuditLogEntry(
                event_id=f"failed-{i}",
                event_type=AuditEventType.LOGIN_ATTEMPT,
                timestamp=datetime.utcnow(),
                user_id="user-123",
                user_type="parent",
                child_id=None,
                action_performed="login attempt",
                resource_type="session",
                resource_id=f"session-{i}",
                data_classification=DataClassification.INTERNAL,
                ip_address="192.168.1.1",
                user_agent="TestAgent",
                success=False  # Failed attempts
            ))
        
        with patch.object(encryption_service, 'get_audit_logs', return_value=mock_logs):
            anomalies = await encryption_service.detect_anomalous_activity("user-123")
        
        # Should detect multiple failed attempts
        failed_attempts_anomaly = next(
            (a for a in anomalies if a["type"] == "multiple_failed_attempts"), None
        )
        assert failed_attempts_anomaly is not None
        assert failed_attempts_anomaly["count"] == 15
        assert failed_attempts_anomaly["severity"] == "high"

    @pytest.mark.asyncio
    async def test_detect_anomalous_activity_multiple_ips(self, encryption_service):
        """Test detection of access from multiple IP addresses."""
        # Mock access from multiple IPs
        mock_logs = []
        for i in range(10):
            mock_logs.append(AuditLogEntry(
                event_id=f"access-{i}",
                event_type=AuditEventType.DATA_ACCESS,
                timestamp=datetime.utcnow(),
                user_id="user-123",
                user_type="parent",
                child_id=None,
                action_performed="data access",
                resource_type="user",
                resource_id="user-123",
                data_classification=DataClassification.INTERNAL,
                ip_address=f"192.168.1.{i}",  # Different IPs
                user_agent="TestAgent",
                success=True
            ))
        
        with patch.object(encryption_service, 'get_audit_logs', return_value=mock_logs):
            anomalies = await encryption_service.detect_anomalous_activity("user-123")
        
        # Should detect multiple IP addresses
        multiple_ips_anomaly = next(
            (a for a in anomalies if a["type"] == "multiple_ip_addresses"), None
        )
        assert multiple_ips_anomaly is not None
        assert multiple_ips_anomaly["count"] == 10
        assert multiple_ips_anomaly["severity"] == "medium"


class TestKeyManagement:
    """Test encryption key management."""

    @pytest.fixture
    async def encryption_service(self):
        """Create DataEncryptionService for key management testing."""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = AsyncMock(spec=True)
            mock_redis.from_url.return_value = mock_redis_instance
            
            service = DataEncryptionService(
                redis_url="redis://localhost:6379/0",
                key_rotation_days=1  # Short rotation for testing
            )
            service.redis = mock_redis_instance
            
            yield service
            
            await service.close()

    @pytest.mark.asyncio
    async def test_rotate_encryption_keys_due(self, encryption_service):
        """Test key rotation when due."""
        # Set last rotation to make it due
        encryption_service.key_info.last_rotated = datetime.utcnow() - timedelta(days=2)
        old_key_id = encryption_service.key_info.key_id
        
        result = await encryption_service.rotate_encryption_keys()
        
        assert result is True
        assert encryption_service.key_info.key_id != old_key_id
        assert encryption_service.key_info.last_rotated is not None
        
        # Should have logged audit event
        assert len(encryption_service._audit_buffer) > 0
        audit_entry = encryption_service._audit_buffer[-1]
        assert audit_entry.event_type == AuditEventType.ENCRYPTION_KEY_ROTATION

    @pytest.mark.asyncio
    async def test_rotate_encryption_keys_not_due(self, encryption_service):
        """Test key rotation when not due."""
        # Set recent rotation
        encryption_service.key_info.last_rotated = datetime.utcnow()
        old_key_id = encryption_service.key_info.key_id
        
        result = await encryption_service.rotate_encryption_keys()
        
        assert result is False
        assert encryption_service.key_info.key_id == old_key_id

    @pytest.mark.asyncio
    async def test_rotate_encryption_keys_first_time(self, encryption_service):
        """Test key rotation for first time (no previous rotation)."""
        # Clear last rotation
        encryption_service.key_info.last_rotated = None
        old_key_id = encryption_service.key_info.key_id
        
        result = await encryption_service.rotate_encryption_keys()
        
        assert result is True
        assert encryption_service.key_info.key_id != old_key_id

    @pytest.mark.asyncio
    async def test_key_rotation_error_handling(self, encryption_service):
        """Test error handling during key rotation."""
        with patch.object(encryption_service, 'log_audit_event', side_effect=Exception("Audit failed")):
            result = await encryption_service.rotate_encryption_keys()
            
            assert result is False  # Should fail gracefully


class TestCOPPACompliance:
    """Test COPPA compliance features."""

    @pytest.fixture
    async def encryption_service(self):
        """Create DataEncryptionService for COPPA testing."""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = AsyncMock(spec=True)
            mock_redis.from_url.return_value = mock_redis_instance
            
            service = DataEncryptionService(
                redis_url="redis://localhost:6379/0",
                audit_retention_days=2555  # 7 years for COPPA
            )
            service.redis = mock_redis_instance
            
            yield service
            
            await service.close()

    @pytest.mark.asyncio
    async def test_log_child_data_access(self, encryption_service):
        """Test logging of child data access for COPPA compliance."""
        await encryption_service.log_child_data_access(
            child_id="child-123",
            accessor_user_id="parent-456",
            accessor_type="parent",
            data_fields=["child_name", "child_age", "preferences"],
            purpose="updating child profile",
            ip_address="192.168.1.1"
        )
        
        # Check audit entry was created
        assert len(encryption_service._audit_buffer) == 1
        entry = encryption_service._audit_buffer[0]
        
        assert entry.event_type == AuditEventType.DATA_ACCESS
        assert entry.child_id == "child-123"
        assert entry.user_id == "parent-456"
        assert entry.data_classification == DataClassification.RESTRICTED
        assert entry.metadata["coppa_compliance"] is True
        assert entry.metadata["data_fields"] == ["child_name", "child_age", "preferences"]

    @pytest.mark.asyncio
    async def test_generate_coppa_compliance_report(self, encryption_service):
        """Test COPPA compliance report generation."""
        # Mock audit logs for child
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        
        mock_logs = [
            AuditLogEntry(
                event_id="access-1",
                event_type=AuditEventType.DATA_ACCESS,
                timestamp=datetime.utcnow(),
                user_id="parent-123",
                user_type="parent",
                child_id="child-456",
                action_performed="accessed child profile",
                resource_type="child",
                resource_id="child-456",
                data_classification=DataClassification.RESTRICTED,
                ip_address="192.168.1.1",
                user_agent="WebApp/1.0",
                success=True
            ),
            AuditLogEntry(
                event_id="update-1",
                event_type=AuditEventType.DATA_UPDATE,
                timestamp=datetime.utcnow(),
                user_id="parent-123",
                user_type="parent",
                child_id="child-456",
                action_performed="updated child preferences",
                resource_type="child",
                resource_id="child-456",
                data_classification=DataClassification.RESTRICTED,
                ip_address="192.168.1.1",
                user_agent="WebApp/1.0",
                success=True
            )
        ]
        
        with patch.object(encryption_service, 'get_audit_logs', return_value=mock_logs):
            report = await encryption_service.generate_coppa_compliance_report(
                child_id="child-456",
                start_date=start_date,
                end_date=end_date
            )
        
        assert report["child_id"] == "child-456"
        assert report["total_events"] == 2
        assert report["data_access_events"] == 1
        assert report["data_modification_events"] == 1
        assert report["compliance_status"] == "COMPLIANT"
        assert report["data_retention_compliant"] is True
        assert report["encryption_status"] == "ENCRYPTED"


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.fixture
    async def encryption_service(self):
        """Create DataEncryptionService for health check testing."""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = AsyncMock(spec=True)
            mock_redis.from_url.return_value = mock_redis_instance
            
            service = DataEncryptionService(redis_url="redis://localhost:6379/0")
            service.redis = mock_redis_instance
            
            yield service
            
            await service.close()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, encryption_service):
        """Test health check when service is healthy."""
        # Mock successful Redis ping
        encryption_service.redis.ping.return_value = True
        
        health = await encryption_service.health_check()
        
        assert health["status"] == "healthy"
        assert health["encryption_working"] is True
        assert health["redis_connected"] is True
        assert "audit_buffer_size" in health
        assert "key_age_days" in health
        assert "security_events_count" in health

    @pytest.mark.asyncio
    async def test_health_check_redis_failure(self, encryption_service):
        """Test health check when Redis is down."""
        # Mock Redis ping failure
        encryption_service.redis.ping.side_effect = Exception("Redis connection failed")
        
        health = await encryption_service.health_check()
        
        assert health["status"] == "unhealthy"
        assert health["redis_connected"] is False

    @pytest.mark.asyncio
    async def test_health_check_encryption_failure(self, encryption_service):
        """Test health check when encryption fails."""
        # Mock encryption failure
        with patch.object(encryption_service, 'encrypt_field', side_effect=Exception("Encryption failed")):
            health = await encryption_service.health_check()
            
            assert health["status"] == "unhealthy"
            assert health["encryption_working"] is False

    @pytest.mark.asyncio
    async def test_health_check_key_rotation_due(self, encryption_service):
        """Test health check indicates when key rotation is due."""
        # Set old key creation date
        encryption_service.key_info.created_at = datetime.utcnow() - timedelta(days=100)
        encryption_service.key_rotation_days = 90
        
        health = await encryption_service.health_check()
        
        assert health["key_rotation_due"] is True
        assert health["key_age_days"] >= 90


class TestFactoryFunction:
    """Test factory function."""

    def test_create_data_encryption_service_coppa_enabled(self):
        """Test factory function with COPPA compliance enabled."""
        with patch('redis.asyncio.Redis'):
            service = create_data_encryption_service(
                redis_url="redis://localhost:6379/1",
                coppa_compliance=True
            )
            
            assert service.audit_retention_days == 2555  # 7 years
            assert service.key_rotation_days == 30       # Monthly

    def test_create_data_encryption_service_coppa_disabled(self):
        """Test factory function with COPPA compliance disabled."""
        with patch('redis.asyncio.Redis'):
            service = create_data_encryption_service(
                redis_url="redis://localhost:6379/1",
                coppa_compliance=False
            )
            
            assert service.audit_retention_days == 365   # 1 year
            assert service.key_rotation_days == 90       # Quarterly


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture
    async def encryption_service(self):
        """Create DataEncryptionService for integration testing."""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = AsyncMock(spec=True)
            mock_redis.from_url.return_value = mock_redis_instance
            
            service = DataEncryptionService(redis_url="redis://localhost:6379/0")
            service.redis = mock_redis_instance
            
            yield service
            
            await service.close()

    @pytest.mark.asyncio
    async def test_complete_child_data_workflow(self, encryption_service):
        """Test complete child data handling workflow."""
        # 1. Encrypt child data
        child_data = {
            "child_name": "Alice",
            "child_age": 8,
            "child_preferences": {"favorite_color": "blue"},
            "child_location": "New York"
        }
        
        encrypted_data = await encryption_service.encrypt_user_data(child_data)
        
        # 2. Log data access
        await encryption_service.log_child_data_access(
            child_id="child-123",
            accessor_user_id="parent-456",
            accessor_type="parent",
            data_fields=list(child_data.keys()),
            purpose="profile_update",
            ip_address="192.168.1.1"
        )
        
        # 3. Decrypt data
        decrypted_data = await encryption_service.decrypt_user_data(encrypted_data)
        
        # 4. Generate compliance report
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow()
        
        with patch.object(encryption_service, 'get_audit_logs') as mock_get_logs:
            mock_get_logs.return_value = encryption_service._audit_buffer
            
            report = await encryption_service.generate_coppa_compliance_report(
                child_id="child-123",
                start_date=start_date,
                end_date=end_date
            )
        
        # Verify workflow completed successfully
        assert decrypted_data == child_data
        assert report["compliance_status"] == "COMPLIANT"
        assert len(encryption_service._audit_buffer) > 0

    @pytest.mark.asyncio
    async def test_security_incident_workflow(self, encryption_service):
        """Test security incident detection and response workflow."""
        # 1. Log suspicious activity
        await encryption_service.log_audit_event(
            event_type=AuditEventType.UNAUTHORIZED_ACCESS,
            action_performed="attempted access to restricted data",
            resource_type="child_data",
            user_id="unknown_user",
            child_id="child-123",
            data_classification=DataClassification.RESTRICTED,
            ip_address="10.0.0.100",
            success=False,
            error_message="Access denied"
        )
        
        # 2. Detect anomalous activity
        mock_failed_logs = []
        for i in range(15):  # Create pattern of failed attempts
            mock_failed_logs.append(AuditLogEntry(
                event_id=f"failed-{i}",
                event_type=AuditEventType.UNAUTHORIZED_ACCESS,
                timestamp=datetime.utcnow(),
                user_id="unknown_user",
                user_type="unknown",
                child_id=None,
                action_performed="failed login",
                resource_type="session",
                resource_id=f"session-{i}",
                data_classification=DataClassification.INTERNAL,
                ip_address="10.0.0.100",
                user_agent="AttackBot",
                success=False
            ))
        
        with patch.object(encryption_service, 'get_audit_logs', return_value=mock_failed_logs):
            anomalies = await encryption_service.detect_anomalous_activity("unknown_user")
        
        # Should detect multiple failed attempts
        assert len(anomalies) > 0
        failed_attempts_anomaly = next(
            (a for a in anomalies if a["type"] == "multiple_failed_attempts"), None
        )
        assert failed_attempts_anomaly is not None
        assert failed_attempts_anomaly["severity"] == "high"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, encryption_service):
        """Test concurrent encryption and audit operations."""
        # Run multiple operations concurrently
        tasks = []
        
        # Encryption tasks
        for i in range(10):
            task = encryption_service.encrypt_field(f"field_{i}", f"value_{i}")
            tasks.append(task)
        
        # Audit logging tasks
        for i in range(10):
            task = encryption_service.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                action_performed=f"concurrent access {i}",
                resource_type="test",
                user_id=f"user-{i}"
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all operations completed (first 10 are encryption results)
        encryption_results = results[:10]
        for result in encryption_results:
            assert isinstance(result, str)  # Encrypted values
            assert not isinstance(result, Exception)
        
        # Check audit buffer has events from concurrent logging
        assert len(encryption_service._audit_buffer) >= 10