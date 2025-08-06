"""
Data Persistence Manager Tests
==============================
Tests for comprehensive data persistence with COPPA compliance and child data protection.
"""

import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid
import hashlib


class DataType(Enum):
    """Types of data being persisted."""
    USER_PROFILE = "user_profile"
    CONVERSATION = "conversation"
    AUDIO_RECORDING = "audio_recording"
    INTERACTION_LOG = "interaction_log"
    PREFERENCE = "preference"
    SAFETY_LOG = "safety_log"
    COPPA_CONSENT = "coppa_consent"


class DataSensitivity(Enum):
    """Data sensitivity levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # Child data under COPPA


@dataclass
class DataRecord:
    """Data record with metadata."""
    record_id: str
    data_type: DataType
    user_id: str
    data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    
    # COPPA compliance fields
    is_child_data: bool = False
    parent_consent: bool = False
    retention_until: Optional[datetime] = None
    
    # Encryption and security
    encrypted: bool = False
    encryption_key_id: Optional[str] = None
    checksum: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "data_type": self.data_type.value,
            "user_id": self.user_id,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sensitivity": self.sensitivity.value,
            "is_child_data": self.is_child_data,
            "parent_consent": self.parent_consent,
            "retention_until": self.retention_until.isoformat() if self.retention_until else None,
            "encrypted": self.encrypted,
            "encryption_key_id": self.encryption_key_id,
            "checksum": self.checksum,
            "metadata": self.metadata
        }
    
    def calculate_checksum(self) -> str:
        """Calculate data integrity checksum."""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def is_expired(self) -> bool:
        """Check if data retention period has expired."""
        if not self.retention_until:
            return False
        return datetime.now() > self.retention_until


class DataPersistenceManager:
    """Advanced data persistence manager with COPPA compliance and child data protection."""
    
    def __init__(self, storage_path: str = None, encryption_service=None):
        self.storage_path = storage_path or tempfile.mkdtemp()
        self.encryption_service = encryption_service
        
        # In-memory cache
        self.cache: Dict[str, DataRecord] = {}
        self.user_data_index: Dict[str, List[str]] = {}  # user_id -> record_ids
        
        # COPPA compliance settings
        self.coppa_mode = True
        self.child_data_retention_days = 30  # COPPA requirement
        self.adult_data_retention_days = 365
        
        # Configuration
        self.auto_encrypt_child_data = True
        self.require_parent_consent = True
        self.enable_data_integrity_checks = True
        
        # Metrics
        self.metrics = {
            "total_records": 0,
            "child_records": 0,
            "encrypted_records": 0,
            "expired_records_cleaned": 0,
            "integrity_violations": 0
        }
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)
    
    async def store_data(
        self,
        data_type: DataType,
        user_id: str,
        data: Dict[str, Any],
        sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
        is_child_data: bool = False,
        parent_consent: bool = False,
        **metadata
    ) -> str:
        """Store data with COPPA compliance checks."""
        # COPPA compliance validation
        if is_child_data and self.coppa_mode:
            if self.require_parent_consent and not parent_consent:
                raise COPPAViolationError("Parent consent required for child data")
            
            # Automatically set high sensitivity for child data
            sensitivity = DataSensitivity.RESTRICTED
        
        # Generate record ID
        record_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Calculate retention period
        retention_days = self.child_data_retention_days if is_child_data else self.adult_data_retention_days
        retention_until = now + timedelta(days=retention_days)
        
        # Create data record
        record = DataRecord(
            record_id=record_id,
            data_type=data_type,
            user_id=user_id,
            data=data.copy(),
            created_at=now,
            updated_at=now,
            sensitivity=sensitivity,
            is_child_data=is_child_data,
            parent_consent=parent_consent,
            retention_until=retention_until,
            metadata=metadata
        )
        
        # Calculate checksum for integrity
        if self.enable_data_integrity_checks:
            record.checksum = record.calculate_checksum()
        
        # Encrypt if required
        if self._should_encrypt(record):
            await self._encrypt_record(record)
        
        # Store record
        await self._persist_record(record)
        
        # Update cache and indexes
        self.cache[record_id] = record
        
        if user_id not in self.user_data_index:
            self.user_data_index[user_id] = []
        self.user_data_index[user_id].append(record_id)
        
        # Update metrics
        self.metrics["total_records"] += 1
        if is_child_data:
            self.metrics["child_records"] += 1
        if record.encrypted:
            self.metrics["encrypted_records"] += 1
        
        return record_id
    
    async def retrieve_data(self, record_id: str, user_id: str = None) -> Optional[DataRecord]:
        """Retrieve data record with access control."""
        # Try cache first
        if record_id in self.cache:
            record = self.cache[record_id]
        else:
            # Load from storage
            record = await self._load_record(record_id)
            if record:
                self.cache[record_id] = record
        
        if not record:
            return None
        
        # Access control check
        if user_id and record.user_id != user_id:
            return None
        
        # Check if expired
        if record.is_expired():
            await self._expire_record(record_id)
            return None
        
        # Decrypt if needed
        if record.encrypted:
            await self._decrypt_record(record)
        
        # Verify integrity
        if self.enable_data_integrity_checks and record.checksum:
            current_checksum = record.calculate_checksum()
            if current_checksum != record.checksum:
                self.metrics["integrity_violations"] += 1
                raise DataIntegrityError(f"Data integrity violation for record {record_id}")
        
        return record
    
    async def update_data(
        self,
        record_id: str,
        data: Dict[str, Any],
        user_id: str = None
    ) -> bool:
        """Update existing data record."""
        record = await self.retrieve_data(record_id, user_id)
        if not record:
            return False
        
        # Update data and metadata
        record.data.update(data)
        record.updated_at = datetime.now()
        
        # Recalculate checksum
        if self.enable_data_integrity_checks:
            record.checksum = record.calculate_checksum()
        
        # Re-encrypt if needed
        if record.encrypted:
            await self._encrypt_record(record)
        
        # Persist changes
        await self._persist_record(record)
        
        return True
    
    async def delete_data(self, record_id: str, user_id: str = None) -> bool:
        """Delete data record with proper cleanup."""
        record = await self.retrieve_data(record_id, user_id)
        if not record:
            return False
        
        # Remove from storage
        await self._delete_record_file(record_id)
        
        # Remove from cache and indexes
        if record_id in self.cache:
            del self.cache[record_id]
        
        if record.user_id in self.user_data_index:
            self.user_data_index[record.user_id] = [
                rid for rid in self.user_data_index[record.user_id]
                if rid != record_id
            ]
        
        # Update metrics
        self.metrics["total_records"] -= 1
        if record.is_child_data:
            self.metrics["child_records"] -= 1
        if record.encrypted:
            self.metrics["encrypted_records"] -= 1
        
        return True
    
    async def get_user_data(
        self,
        user_id: str,
        data_type: DataType = None,
        limit: int = 100
    ) -> List[DataRecord]:
        """Get all data records for a user."""
        record_ids = self.user_data_index.get(user_id, [])
        records = []
        
        for record_id in record_ids[:limit]:
            record = await self.retrieve_data(record_id, user_id)
            if record:
                if data_type is None or record.data_type == data_type:
                    records.append(record)
        
        return records
    
    async def get_child_data_records(self) -> List[DataRecord]:
        """Get all child data records for compliance monitoring."""
        child_records = []
        
        for record_id, record in self.cache.items():
            if record.is_child_data:
                child_records.append(record)
        
        return child_records
    
    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user data (GDPR/COPPA compliance)."""
        user_records = await self.get_user_data(user_id)
        
        export_data = {
            "user_id": user_id,
            "export_timestamp": datetime.now().isoformat(),
            "total_records": len(user_records),
            "records": []
        }
        
        for record in user_records:
            export_data["records"].append({
                "record_id": record.record_id,
                "data_type": record.data_type.value,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
                "data": record.data,
                "is_child_data": record.is_child_data,
                "parent_consent": record.parent_consent
            })
        
        return export_data
    
    async def delete_user_data(self, user_id: str) -> int:
        """Delete all data for a user (right to be forgotten)."""
        record_ids = self.user_data_index.get(user_id, []).copy()
        deleted_count = 0
        
        for record_id in record_ids:
            success = await self.delete_data(record_id, user_id)
            if success:
                deleted_count += 1
        
        # Clean up user index
        if user_id in self.user_data_index:
            del self.user_data_index[user_id]
        
        return deleted_count
    
    async def start_cleanup_task(self):
        """Start background cleanup task for expired data."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self):
        """Background cleanup loop for expired data."""
        while self._running:
            try:
                await self._cleanup_expired_data()
                await asyncio.sleep(3600)  # Run every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Cleanup error: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes
    
    async def _cleanup_expired_data(self):
        """Clean up expired data records."""
        expired_records = []
        
        for record_id, record in self.cache.items():
            if record.is_expired():
                expired_records.append(record_id)
        
        for record_id in expired_records:
            await self._expire_record(record_id)
    
    async def _expire_record(self, record_id: str):
        """Mark record as expired and clean up."""
        if record_id in self.cache:
            record = self.cache[record_id]
            
            # Log expiration for audit
            print(f"Expiring record {record_id} for user {record.user_id}")
            
            # Delete the record
            await self.delete_data(record_id)
            
            self.metrics["expired_records_cleaned"] += 1
    
    def _should_encrypt(self, record: DataRecord) -> bool:
        """Determine if record should be encrypted."""
        if record.is_child_data and self.auto_encrypt_child_data:
            return True
        
        if record.sensitivity in [DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED]:
            return True
        
        return False
    
    async def _encrypt_record(self, record: DataRecord):
        """Encrypt record data."""
        if not self.encryption_service:
            # Mock encryption for testing
            record.encrypted = True
            record.encryption_key_id = "mock_key_001"
            return
        
        try:
            encrypted_data = await self.encryption_service.encrypt(
                json.dumps(record.data),
                record.user_id
            )
            
            record.data = {"encrypted": encrypted_data}
            record.encrypted = True
            record.encryption_key_id = "key_001"  # Would be actual key ID
            
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt record: {e}")
    
    async def _decrypt_record(self, record: DataRecord):
        """Decrypt record data."""
        if not record.encrypted:
            return
        
        if not self.encryption_service:
            # Mock decryption for testing
            return
        
        try:
            encrypted_data = record.data.get("encrypted")
            if encrypted_data:
                decrypted_data = await self.encryption_service.decrypt(
                    encrypted_data,
                    record.encryption_key_id
                )
                record.data = json.loads(decrypted_data)
                
        except Exception as e:
            raise DecryptionError(f"Failed to decrypt record: {e}")
    
    async def _persist_record(self, record: DataRecord):
        """Persist record to storage."""
        file_path = os.path.join(self.storage_path, f"{record.record_id}.json")
        
        try:
            with open(file_path, 'w') as f:
                json.dump(record.to_dict(), f, default=str, indent=2)
                
        except Exception as e:
            raise PersistenceError(f"Failed to persist record: {e}")
    
    async def _load_record(self, record_id: str) -> Optional[DataRecord]:
        """Load record from storage."""
        file_path = os.path.join(self.storage_path, f"{record_id}.json")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            return DataRecord(
                record_id=data["record_id"],
                data_type=DataType(data["data_type"]),
                user_id=data["user_id"],
                data=data["data"],
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                sensitivity=DataSensitivity(data["sensitivity"]),
                is_child_data=data.get("is_child_data", False),
                parent_consent=data.get("parent_consent", False),
                retention_until=datetime.fromisoformat(data["retention_until"]) if data.get("retention_until") else None,
                encrypted=data.get("encrypted", False),
                encryption_key_id=data.get("encryption_key_id"),
                checksum=data.get("checksum"),
                metadata=data.get("metadata", {})
            )
            
        except Exception as e:
            print(f"Failed to load record {record_id}: {e}")
            return None
    
    async def _delete_record_file(self, record_id: str):
        """Delete record file from storage."""
        file_path = os.path.join(self.storage_path, f"{record_id}.json")
        
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Failed to delete record file {record_id}: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get persistence metrics."""
        return self.metrics.copy()
    
    async def get_compliance_report(self) -> Dict[str, Any]:
        """Get COPPA compliance report."""
        child_records = await self.get_child_data_records()
        
        return {
            "total_child_records": len(child_records),
            "child_records_with_consent": len([r for r in child_records if r.parent_consent]),
            "child_records_without_consent": len([r for r in child_records if not r.parent_consent]),
            "encrypted_child_records": len([r for r in child_records if r.encrypted]),
            "retention_compliance": {
                "records_within_retention": len([r for r in child_records if not r.is_expired()]),
                "records_expired": len([r for r in child_records if r.is_expired()])
            },
            "metrics": self.get_metrics(),
            "timestamp": datetime.now().isoformat()
        }


class COPPAViolationError(Exception):
    """Exception raised for COPPA compliance violations."""
    pass


class DataIntegrityError(Exception):
    """Exception raised for data integrity violations."""
    pass


class EncryptionError(Exception):
    """Exception raised for encryption failures."""
    pass


class DecryptionError(Exception):
    """Exception raised for decryption failures."""
    pass


class PersistenceError(Exception):
    """Exception raised for persistence failures."""
    pass


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def persistence_manager(temp_storage):
    """Create persistence manager for testing."""
    return DataPersistenceManager(storage_path=temp_storage)


@pytest.fixture
def mock_encryption_service():
    """Mock encryption service for testing."""
    service = AsyncMock(spec=True)
    service.encrypt = AsyncMock(return_value="encrypted_data_mock")
    service.decrypt = AsyncMock(return_value='{"test": "decrypted_data"}')
    return service


@pytest.mark.asyncio
class TestDataPersistenceManager:
    """Test data persistence manager functionality."""
    
    async def test_basic_data_storage(self, persistence_manager):
        """Test basic data storage and retrieval."""
        # Store data
        record_id = await persistence_manager.store_data(
            data_type=DataType.USER_PROFILE,
            user_id="user_123",
            data={"name": "John Doe", "age": 35, "preferences": {"theme": "dark"}}
        )
        
        assert record_id is not None
        
        # Retrieve data
        record = await persistence_manager.retrieve_data(record_id, "user_123")
        
        assert record is not None
        assert record.record_id == record_id
        assert record.user_id == "user_123"
        assert record.data_type == DataType.USER_PROFILE
        assert record.data["name"] == "John Doe"
        assert record.data["age"] == 35
    
    async def test_child_data_storage_with_consent(self, persistence_manager):
        """Test child data storage with parent consent."""
        # Store child data with consent
        record_id = await persistence_manager.store_data(
            data_type=DataType.CONVERSATION,
            user_id="child_123",
            data={"message": "Hello teddy!", "timestamp": "2024-01-01T12:00:00"},
            is_child_data=True,
            parent_consent=True
        )
        
        # Retrieve and verify
        record = await persistence_manager.retrieve_data(record_id, "child_123")
        
        assert record.is_child_data is True
        assert record.parent_consent is True
        assert record.sensitivity == DataSensitivity.RESTRICTED
        assert record.encrypted is True  # Should be auto-encrypted
    
    async def test_child_data_storage_without_consent(self, persistence_manager):
        """Test child data storage without parent consent (should fail)."""
        with pytest.raises(COPPAViolationError):
            await persistence_manager.store_data(
                data_type=DataType.CONVERSATION,
                user_id="child_123",
                data={"message": "Hello teddy!"},
                is_child_data=True,
                parent_consent=False
            )
    
    async def test_data_update(self, persistence_manager):
        """Test data record updates."""
        # Store initial data
        record_id = await persistence_manager.store_data(
            data_type=DataType.PREFERENCE,
            user_id="user_123",
            data={"volume": 0.5, "voice_speed": 1.0}
        )
        
        # Update data
        success = await persistence_manager.update_data(
            record_id,
            {"volume": 0.8, "new_setting": "enabled"},
            "user_123"
        )
        
        assert success is True
        
        # Verify update
        record = await persistence_manager.retrieve_data(record_id, "user_123")
        assert record.data["volume"] == 0.8
        assert record.data["voice_speed"] == 1.0  # Should remain
        assert record.data["new_setting"] == "enabled"
    
    async def test_data_deletion(self, persistence_manager):
        """Test data record deletion."""
        # Store data
        record_id = await persistence_manager.store_data(
            data_type=DataType.INTERACTION_LOG,
            user_id="user_123",
            data={"action": "button_click", "timestamp": "2024-01-01T12:00:00"}
        )
        
        # Delete data
        success = await persistence_manager.delete_data(record_id, "user_123")
        assert success is True
        
        # Verify deletion
        record = await persistence_manager.retrieve_data(record_id, "user_123")
        assert record is None
    
    async def test_user_data_retrieval(self, persistence_manager):
        """Test retrieving all data for a user."""
        user_id = "user_123"
        
        # Store multiple records
        record_ids = []
        for i in range(3):
            record_id = await persistence_manager.store_data(
                data_type=DataType.CONVERSATION,
                user_id=user_id,
                data={"message": f"Message {i}", "index": i}
            )
            record_ids.append(record_id)
        
        # Retrieve user data
        user_records = await persistence_manager.get_user_data(user_id)
        
        assert len(user_records) == 3
        assert all(record.user_id == user_id for record in user_records)
        
        # Test filtering by data type
        conversation_records = await persistence_manager.get_user_data(
            user_id,
            data_type=DataType.CONVERSATION
        )
        assert len(conversation_records) == 3
        assert all(record.data_type == DataType.CONVERSATION for record in conversation_records)
    
    async def test_data_encryption(self, persistence_manager, mock_encryption_service):
        """Test data encryption for sensitive records."""
        persistence_manager.encryption_service = mock_encryption_service
        
        # Store confidential data
        record_id = await persistence_manager.store_data(
            data_type=DataType.SAFETY_LOG,
            user_id="user_123",
            data={"incident": "inappropriate_content", "details": "blocked content"},
            sensitivity=DataSensitivity.CONFIDENTIAL
        )
        
        # Verify encryption was applied
        record = await persistence_manager.retrieve_data(record_id, "user_123")
        assert record.encrypted is True
        assert record.encryption_key_id is not None
        
        # Verify encryption service was called
        mock_encryption_service.encrypt.assert_called_once()
    
    async def test_data_integrity_checks(self, persistence_manager):
        """Test data integrity verification."""
        # Store data with integrity checks enabled
        record_id = await persistence_manager.store_data(
            data_type=DataType.USER_PROFILE,
            user_id="user_123",
            data={"name": "John Doe", "email": "john@example.com"}
        )
        
        # Retrieve and verify checksum was calculated
        record = await persistence_manager.retrieve_data(record_id, "user_123")
        assert record.checksum is not None
        
        # Manually corrupt data and verify integrity check fails
        record.data["name"] = "Corrupted Name"
        
        with pytest.raises(DataIntegrityError):
            await persistence_manager.retrieve_data(record_id, "user_123")
    
    async def test_data_retention_and_expiration(self, persistence_manager):
        """Test data retention and automatic expiration."""
        # Set short retention for testing
        persistence_manager.child_data_retention_days = 0  # Immediate expiration
        
        # Store child data
        record_id = await persistence_manager.store_data(
            data_type=DataType.CONVERSATION,
            user_id="child_123",
            data={"message": "Hello!"},
            is_child_data=True,
            parent_consent=True
        )
        
        # Manually set expiration to past
        record = persistence_manager.cache[record_id]
        record.retention_until = datetime.now() - timedelta(seconds=1)
        
        # Try to retrieve (should return None due to expiration)
        retrieved_record = await persistence_manager.retrieve_data(record_id, "child_123")
        assert retrieved_record is None
        
        # Verify record was cleaned up
        assert record_id not in persistence_manager.cache
    
    async def test_user_data_export(self, persistence_manager):
        """Test user data export for GDPR/COPPA compliance."""
        user_id = "user_123"
        
        # Store various data types
        await persistence_manager.store_data(
            DataType.USER_PROFILE, user_id,
            {"name": "John Doe", "age": 35}
        )
        
        await persistence_manager.store_data(
            DataType.CONVERSATION, user_id,
            {"message": "Hello teddy!", "timestamp": "2024-01-01T12:00:00"}
        )
        
        # Export user data
        export_data = await persistence_manager.export_user_data(user_id)
        
        assert export_data["user_id"] == user_id
        assert export_data["total_records"] == 2
        assert len(export_data["records"]) == 2
        
        # Verify export contains all necessary fields
        for record in export_data["records"]:
            assert "record_id" in record
            assert "data_type" in record
            assert "created_at" in record
            assert "data" in record
    
    async def test_user_data_deletion(self, persistence_manager):
        """Test complete user data deletion (right to be forgotten)."""
        user_id = "user_123"
        
        # Store multiple records
        for i in range(3):
            await persistence_manager.store_data(
                DataType.CONVERSATION, user_id,
                {"message": f"Message {i}"}
            )
        
        # Verify data exists
        user_records = await persistence_manager.get_user_data(user_id)
        assert len(user_records) == 3
        
        # Delete all user data
        deleted_count = await persistence_manager.delete_user_data(user_id)
        assert deleted_count == 3
        
        # Verify all data deleted
        user_records = await persistence_manager.get_user_data(user_id)
        assert len(user_records) == 0
        
        # Verify user index cleaned up
        assert user_id not in persistence_manager.user_data_index
    
    async def test_access_control(self, persistence_manager):
        """Test access control for data retrieval."""
        # Store data for user A
        record_id = await persistence_manager.store_data(
            DataType.USER_PROFILE,
            user_id="user_a",
            data={"name": "User A", "secret": "confidential"}
        )
        
        # User A can access their data
        record = await persistence_manager.retrieve_data(record_id, "user_a")
        assert record is not None
        assert record.data["name"] == "User A"
        
        # User B cannot access User A's data
        record = await persistence_manager.retrieve_data(record_id, "user_b")
        assert record is None
    
    async def test_child_data_monitoring(self, persistence_manager):
        """Test child data monitoring for compliance."""
        # Store child data
        await persistence_manager.store_data(
            DataType.CONVERSATION, "child_1",
            {"message": "Hello!"}, is_child_data=True, parent_consent=True
        )
        
        await persistence_manager.store_data(
            DataType.AUDIO_RECORDING, "child_2",
            {"duration": 30, "content": "story_request"}, is_child_data=True, parent_consent=True
        )
        
        # Get child data records
        child_records = await persistence_manager.get_child_data_records()
        
        assert len(child_records) == 2
        assert all(record.is_child_data for record in child_records)
        assert all(record.parent_consent for record in child_records)
    
    async def test_compliance_reporting(self, persistence_manager):
        """Test COPPA compliance reporting."""
        # Store mixed child data
        await persistence_manager.store_data(
            DataType.CONVERSATION, "child_1",
            {"message": "Hello!"}, is_child_data=True, parent_consent=True
        )
        
        # Temporarily disable consent requirement for testing
        persistence_manager.require_parent_consent = False
        await persistence_manager.store_data(
            DataType.CONVERSATION, "child_2",
            {"message": "Hi!"}, is_child_data=True, parent_consent=False
        )
        persistence_manager.require_parent_consent = True
        
        # Get compliance report
        report = await persistence_manager.get_compliance_report()
        
        assert report["total_child_records"] == 2
        assert report["child_records_with_consent"] == 1
        assert report["child_records_without_consent"] == 1
        assert report["encrypted_child_records"] == 2  # Both should be encrypted
    
    async def test_background_cleanup(self, persistence_manager):
        """Test background cleanup of expired data."""
        # Set short retention for testing
        persistence_manager.child_data_retention_days = 0
        
        # Store child data that will expire immediately
        record_id = await persistence_manager.store_data(
            DataType.CONVERSATION, "child_123",
            {"message": "Hello!"}, is_child_data=True, parent_consent=True
        )
        
        # Manually expire the record
        record = persistence_manager.cache[record_id]
        record.retention_until = datetime.now() - timedelta(seconds=1)
        
        # Run cleanup
        await persistence_manager._cleanup_expired_data()
        
        # Verify record was cleaned up
        assert record_id not in persistence_manager.cache
        assert persistence_manager.metrics["expired_records_cleaned"] == 1
    
    async def test_metrics_collection(self, persistence_manager):
        """Test metrics collection."""
        # Store various types of data
        await persistence_manager.store_data(
            DataType.USER_PROFILE, "user_1", {"name": "User 1"}
        )
        
        await persistence_manager.store_data(
            DataType.CONVERSATION, "child_1", {"message": "Hello!"},
            is_child_data=True, parent_consent=True
        )
        
        await persistence_manager.store_data(
            DataType.SAFETY_LOG, "user_2", {"incident": "blocked_content"},
            sensitivity=DataSensitivity.CONFIDENTIAL
        )
        
        # Get metrics
        metrics = persistence_manager.get_metrics()
        
        assert metrics["total_records"] == 3
        assert metrics["child_records"] == 1
        assert metrics["encrypted_records"] >= 1  # At least child data and confidential data
    
    async def test_persistence_across_restarts(self, persistence_manager, temp_storage):
        """Test data persistence across manager restarts."""
        # Store data
        record_id = await persistence_manager.store_data(
            DataType.USER_PROFILE, "user_123",
            {"name": "John Doe", "persistent": True}
        )
        
        # Create new manager instance with same storage
        new_manager = DataPersistenceManager(storage_path=temp_storage)
        
        # Retrieve data with new manager
        record = await new_manager.retrieve_data(record_id, "user_123")
        
        assert record is not None
        assert record.data["name"] == "John Doe"
        assert record.data["persistent"] is True
    
    async def test_concurrent_operations(self, persistence_manager):
        """Test concurrent data operations."""
        user_id = "user_123"
        
        # Define concurrent operations
        async def store_data(index: int):
            return await persistence_manager.store_data(
                DataType.CONVERSATION, user_id,
                {"message": f"Concurrent message {index}", "index": index}
            )
        
        # Execute concurrent stores
        tasks = [store_data(i) for i in range(10)]
        record_ids = await asyncio.gather(*tasks)
        
        # Verify all records stored
        assert len(record_ids) == 10
        assert len(set(record_ids)) == 10  # All unique
        
        # Verify all records retrievable
        user_records = await persistence_manager.get_user_data(user_id)
        assert len(user_records) == 10