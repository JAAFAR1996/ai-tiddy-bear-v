"""
Tests for Backup Orchestrator.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from dataclasses import dataclass

from src.infrastructure.backup.orchestrator import (
    BackupOrchestrator,
    BackupJob,
    BackupResult,
    BackupTier,
    BackupStatus
)


class TestBackupJob:
    """Test backup job configuration."""

    def test_backup_job_creation(self):
        """Test backup job creation."""
        job = BackupJob(
            id="test-job",
            tier=BackupTier.DAILY,
            components=["database", "files"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            encryption_enabled=True,
            coppa_compliance=True
        )
        
        assert job.id == "test-job"
        assert job.tier == BackupTier.DAILY
        assert job.components == ["database", "files"]
        assert job.retention_days == 30
        assert job.encryption_enabled is True
        assert job.coppa_compliance is True
        assert job.metadata == {}

    def test_backup_job_defaults(self):
        """Test backup job default values."""
        job = BackupJob(
            id="default-job",
            tier=BackupTier.HOURLY,
            components=["database"],
            schedule_cron="0 * * * *",
            retention_days=7
        )
        
        assert job.encryption_enabled is True
        assert job.compression_enabled is True
        assert job.coppa_compliance is True
        assert job.metadata == {}


class TestBackupResult:
    """Test backup result data structure."""

    def test_backup_result_creation(self):
        """Test backup result creation."""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(minutes=30)
        
        result = BackupResult(
            job_id="test-job",
            start_time=start_time,
            end_time=end_time,
            status=BackupStatus.COMPLETED,
            components={"database": True, "files": True},
            backup_paths=["/backup/db.sql", "/backup/files.tar"],
            size_bytes=1024000,
            checksum="abc123def456",
            coppa_verified=True
        )
        
        assert result.job_id == "test-job"
        assert result.status == BackupStatus.COMPLETED
        assert result.components["database"] is True
        assert result.size_bytes == 1024000
        assert result.coppa_verified is True
        assert result.error_message is None


class TestBackupOrchestrator:
    """Test backup orchestrator functionality."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services."""
        return {
            'database_service': AsyncMock(),
            'file_service': AsyncMock(),
            'config_service': AsyncMock(),
            'monitoring_service': AsyncMock(),
            'metrics_collector': Mock()
        }

    @pytest.fixture
    def orchestrator(self, mock_services):
        """Create backup orchestrator with mocked services."""
        return BackupOrchestrator(**mock_services)

    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator.database_service is not None
        assert orchestrator.file_service is not None
        assert orchestrator.config_service is not None
        assert orchestrator.monitoring_service is not None
        assert orchestrator.metrics_collector is not None
        
        # Check default backup tiers
        assert BackupTier.HOURLY in orchestrator.backup_tiers
        assert BackupTier.DAILY in orchestrator.backup_tiers
        assert BackupTier.WEEKLY in orchestrator.backup_tiers
        assert BackupTier.MONTHLY in orchestrator.backup_tiers

    def test_initialize_backup_tiers(self, orchestrator):
        """Test backup tier initialization."""
        tiers = orchestrator._initialize_backup_tiers()
        
        # Check hourly backup
        hourly = tiers[BackupTier.HOURLY]
        assert hourly.tier == BackupTier.HOURLY
        assert hourly.components == ["database"]
        assert hourly.retention_days == 7
        assert hourly.coppa_compliance is True
        
        # Check daily backup
        daily = tiers[BackupTier.DAILY]
        assert daily.tier == BackupTier.DAILY
        assert "database" in daily.components
        assert "files" in daily.components
        assert "config" in daily.components
        assert daily.retention_days == 90
        
        # Check monthly backup (long retention for compliance)
        monthly = tiers[BackupTier.MONTHLY]
        assert monthly.retention_days == 2555  # 7 years

    @pytest.mark.asyncio
    async def test_schedule_backup_success(self, orchestrator):
        """Test successful backup scheduling."""
        job = BackupJob(
            id="test-schedule",
            tier=BackupTier.DAILY,
            components=["database"],
            schedule_cron="0 2 * * *",
            retention_days=30
        )
        
        with patch.object(orchestrator, '_execute_backup_job', new_callable=AsyncMock) as mock_execute:
            job_id = await orchestrator.schedule_backup(job)
            
            assert job_id == "test-schedule"
            assert job_id in orchestrator.active_jobs
            
            # Verify metrics were updated
            orchestrator.metrics_collector.increment_counter.assert_called_with(
                "backup_jobs_scheduled_total",
                {"tier": "daily"}
            )

    @pytest.mark.asyncio
    async def test_validate_backup_job_success(self, orchestrator):
        """Test successful backup job validation."""
        job = BackupJob(
            id="valid-job",
            tier=BackupTier.DAILY,
            components=["database", "files"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            encryption_enabled=True,
            coppa_compliance=True
        )
        
        # Should not raise exception
        await orchestrator._validate_backup_job(job)

    @pytest.mark.asyncio
    async def test_validate_backup_job_no_components(self, orchestrator):
        """Test backup job validation with no components."""
        job = BackupJob(
            id="invalid-job",
            tier=BackupTier.DAILY,
            components=[],
            schedule_cron="0 2 * * *",
            retention_days=30
        )
        
        with pytest.raises(ValueError, match="must specify at least one component"):
            await orchestrator._validate_backup_job(job)

    @pytest.mark.asyncio
    async def test_validate_backup_job_coppa_no_encryption(self, orchestrator):
        """Test backup job validation with COPPA but no encryption."""
        job = BackupJob(
            id="invalid-coppa",
            tier=BackupTier.DAILY,
            components=["database"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            encryption_enabled=False,
            coppa_compliance=True
        )
        
        with pytest.raises(ValueError, match="COPPA compliance requires encryption"):
            await orchestrator._validate_backup_job(job)

    @pytest.mark.asyncio
    async def test_validate_backup_job_missing_service(self, orchestrator):
        """Test backup job validation with missing service."""
        # Remove database service
        orchestrator.database_service = None
        
        job = BackupJob(
            id="missing-service",
            tier=BackupTier.DAILY,
            components=["database"],
            schedule_cron="0 2 * * *",
            retention_days=30
        )
        
        with pytest.raises(ValueError, match="Database service not configured"):
            await orchestrator._validate_backup_job(job)

    @pytest.mark.asyncio
    async def test_execute_backup_job_success(self, orchestrator):
        """Test successful backup job execution."""
        job = BackupJob(
            id="execute-test",
            tier=BackupTier.DAILY,
            components=["database", "files"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            coppa_compliance=True
        )
        
        # Mock component backup results
        db_result = Mock()
        db_result.success = True
        db_result.paths = ["/backup/db.sql"]
        db_result.size_bytes = 500000
        
        file_result = Mock()
        file_result.success = True
        file_result.paths = ["/backup/files.tar"]
        file_result.size_bytes = 1000000
        
        with patch.object(orchestrator, '_backup_component', side_effect=[db_result, file_result]):
            with patch.object(orchestrator, '_verify_coppa_compliance_pre_backup', new_callable=AsyncMock):
                with patch.object(orchestrator, '_verify_backup_integrity', new_callable=AsyncMock):
                    with patch.object(orchestrator, '_verify_coppa_compliance_post_backup', return_value=True):
                        with patch.object(orchestrator, '_notify_backup_completion', new_callable=AsyncMock):
                            result = await orchestrator._execute_backup_job(job)
                            
                            assert result.status == BackupStatus.VERIFIED
                            assert result.components["database"] is True
                            assert result.components["files"] is True
                            assert result.size_bytes == 1500000
                            assert result.coppa_verified is True
                            assert len(result.backup_paths) == 2

    @pytest.mark.asyncio
    async def test_execute_backup_job_component_failure(self, orchestrator):
        """Test backup job execution with component failure."""
        job = BackupJob(
            id="fail-test",
            tier=BackupTier.DAILY,
            components=["database", "files"],
            schedule_cron="0 2 * * *",
            retention_days=30
        )
        
        # Mock one successful, one failed component
        db_result = Mock()
        db_result.success = True
        db_result.paths = ["/backup/db.sql"]
        db_result.size_bytes = 500000
        
        with patch.object(orchestrator, '_backup_component', side_effect=[db_result, Exception("File backup failed")]):
            with patch.object(orchestrator, '_notify_backup_failure', new_callable=AsyncMock):
                result = await orchestrator._execute_backup_job(job)
                
                assert result.status == BackupStatus.FAILED
                assert result.components["database"] is True
                assert result.components["files"] is False
                assert "File backup failed" in result.error_message

    @pytest.mark.asyncio
    async def test_backup_component_database(self, orchestrator):
        """Test database component backup."""
        job = BackupJob(
            id="db-test",
            tier=BackupTier.DAILY,
            components=["database"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            encryption_enabled=True,
            compression_enabled=True,
            coppa_compliance=True
        )
        
        expected_result = Mock()
        orchestrator.database_service.create_backup.return_value = expected_result
        
        result = await orchestrator._backup_component("database", job)
        
        assert result == expected_result
        orchestrator.database_service.create_backup.assert_called_once_with(
            encryption=True,
            compression=True,
            coppa_compliant=True
        )

    @pytest.mark.asyncio
    async def test_backup_component_files(self, orchestrator):
        """Test files component backup."""
        job = BackupJob(
            id="files-test",
            tier=BackupTier.DAILY,
            components=["files"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            encryption_enabled=True,
            compression_enabled=False
        )
        
        expected_result = Mock()
        orchestrator.file_service.create_backup.return_value = expected_result
        
        result = await orchestrator._backup_component("files", job)
        
        assert result == expected_result
        orchestrator.file_service.create_backup.assert_called_once_with(
            encryption=True,
            compression=False,
            coppa_compliant=True
        )

    @pytest.mark.asyncio
    async def test_backup_component_config(self, orchestrator):
        """Test config component backup."""
        job = BackupJob(
            id="config-test",
            tier=BackupTier.DAILY,
            components=["config"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            encryption_enabled=True
        )
        
        expected_result = Mock()
        orchestrator.config_service.create_backup.return_value = expected_result
        
        result = await orchestrator._backup_component("config", job)
        
        assert result == expected_result
        orchestrator.config_service.create_backup.assert_called_once_with(
            encryption=True,
            compression=True
        )

    @pytest.mark.asyncio
    async def test_backup_component_unknown(self, orchestrator):
        """Test backup of unknown component."""
        job = BackupJob(
            id="unknown-test",
            tier=BackupTier.DAILY,
            components=["unknown"],
            schedule_cron="0 2 * * *",
            retention_days=30
        )
        
        with pytest.raises(ValueError, match="Unknown backup component: unknown"):
            await orchestrator._backup_component("unknown", job)

    @pytest.mark.asyncio
    async def test_verify_coppa_compliance_pre_backup(self, orchestrator):
        """Test COPPA compliance verification before backup."""
        # Should complete without error
        await orchestrator._verify_coppa_compliance_pre_backup()

    @pytest.mark.asyncio
    async def test_verify_coppa_compliance_post_backup(self, orchestrator):
        """Test COPPA compliance verification after backup."""
        result = BackupResult(
            job_id="coppa-test",
            start_time=datetime.utcnow(),
            end_time=None,
            status=BackupStatus.IN_PROGRESS,
            components={},
            backup_paths=["/backup/test.enc"],
            size_bytes=1000,
            checksum=""
        )
        
        with patch.object(orchestrator, '_verify_backup_encryption', return_value=True):
            with patch.object(orchestrator, '_scan_backup_for_sensitive_data', return_value=True):
                with patch.object(orchestrator, '_verify_backup_access_controls', return_value=True):
                    verified = await orchestrator._verify_coppa_compliance_post_backup(result)
                    
                    assert verified is True

    @pytest.mark.asyncio
    async def test_verify_coppa_compliance_post_backup_failure(self, orchestrator):
        """Test COPPA compliance verification failure."""
        result = BackupResult(
            job_id="coppa-fail-test",
            start_time=datetime.utcnow(),
            end_time=None,
            status=BackupStatus.IN_PROGRESS,
            components={},
            backup_paths=["/backup/test.txt"],  # Not encrypted
            size_bytes=1000,
            checksum=""
        )
        
        with patch.object(orchestrator, '_verify_backup_encryption', return_value=False):
            verified = await orchestrator._verify_coppa_compliance_post_backup(result)
            
            assert verified is False

    def test_verify_backup_encryption(self, orchestrator):
        """Test backup encryption verification."""
        # Test encrypted files
        encrypted_paths = ["/backup/db.enc", "/backup/files.enc"]
        assert orchestrator._verify_backup_encryption(encrypted_paths) is True
        
        # Test unencrypted files
        unencrypted_paths = ["/backup/db.sql", "/backup/files.tar"]
        assert orchestrator._verify_backup_encryption(unencrypted_paths) is False

    @pytest.mark.asyncio
    async def test_scan_backup_for_sensitive_data(self, orchestrator):
        """Test scanning backup for sensitive data."""
        backup_paths = ["/backup/test.enc"]
        
        # Mock implementation always returns True
        result = await orchestrator._scan_backup_for_sensitive_data(backup_paths)
        assert result is True

    def test_verify_backup_access_controls(self, orchestrator):
        """Test backup access controls verification."""
        import tempfile
        import os
        import stat
        
        # Create temporary file with proper permissions
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            # Set restrictive permissions (owner only)
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            
            result = orchestrator._verify_backup_access_controls([temp_path])
            assert result is True
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_verify_backup_integrity(self, orchestrator):
        """Test backup integrity verification."""
        import tempfile
        
        # Create temporary backup files
        with tempfile.NamedTemporaryFile(delete=False) as temp1:
            temp1.write(b"backup content 1")
            temp1_path = temp1.name
            
        with tempfile.NamedTemporaryFile(delete=False) as temp2:
            temp2.write(b"backup content 2")
            temp2_path = temp2.name
        
        try:
            result = BackupResult(
                job_id="integrity-test",
                start_time=datetime.utcnow(),
                end_time=None,
                status=BackupStatus.IN_PROGRESS,
                components={},
                backup_paths=[temp1_path, temp2_path],
                size_bytes=1000,
                checksum=""
            )
            
            await orchestrator._verify_backup_integrity(result)
            
            # Checksum should be calculated
            assert result.checksum != ""
            assert len(result.checksum) == 64  # SHA256 hex length
            
        finally:
            os.unlink(temp1_path)
            os.unlink(temp2_path)

    @pytest.mark.asyncio
    async def test_notify_backup_completion(self, orchestrator):
        """Test backup completion notification."""
        result = BackupResult(
            job_id="notify-test",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(minutes=30),
            status=BackupStatus.COMPLETED,
            components={"database": True},
            backup_paths=["/backup/db.sql"],
            size_bytes=1024000,
            checksum="abc123",
            coppa_verified=True
        )
        
        await orchestrator._notify_backup_completion(result)
        
        orchestrator.monitoring_service.send_backup_notification.assert_called_once()
        call_args = orchestrator.monitoring_service.send_backup_notification.call_args[1]
        assert call_args["job_id"] == "notify-test"
        assert call_args["status"] == "completed"
        assert call_args["coppa_verified"] is True

    @pytest.mark.asyncio
    async def test_notify_backup_failure(self, orchestrator):
        """Test backup failure notification."""
        result = BackupResult(
            job_id="fail-notify-test",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(minutes=5),
            status=BackupStatus.FAILED,
            components={"database": False},
            backup_paths=[],
            size_bytes=0,
            checksum="",
            error_message="Database connection failed"
        )
        
        await orchestrator._notify_backup_failure(result)
        
        orchestrator.monitoring_service.send_backup_alert.assert_called_once()
        call_args = orchestrator.monitoring_service.send_backup_alert.call_args[1]
        assert call_args["job_id"] == "fail-notify-test"
        assert call_args["error"] == "Database connection failed"

    def test_update_backup_metrics(self, orchestrator):
        """Test backup metrics update."""
        result = BackupResult(
            job_id="metrics-test",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(minutes=15),
            status=BackupStatus.COMPLETED,
            components={"database": True},
            backup_paths=["/backup/db.sql"],
            size_bytes=2048000,
            checksum="def456"
        )
        
        orchestrator._update_backup_metrics(result)
        
        # Verify metrics calls
        assert orchestrator.metrics_collector.increment_counter.call_count >= 1
        assert orchestrator.metrics_collector.observe_histogram.call_count >= 2
        
        # Check specific metric calls
        counter_calls = orchestrator.metrics_collector.increment_counter.call_args_list
        histogram_calls = orchestrator.metrics_collector.observe_histogram.call_args_list
        
        # Verify backup completion counter
        completion_call = next(call for call in counter_calls if call[0][0] == "backup_jobs_completed_total")
        assert completion_call[0][1]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, orchestrator):
        """Test cleanup of old backups."""
        with patch.object(orchestrator, '_cleanup_tier_backups', return_value=5) as mock_cleanup:
            await orchestrator.cleanup_old_backups()
            
            # Should call cleanup for each tier
            assert mock_cleanup.call_count == len(orchestrator.backup_tiers)
            
            # Verify metrics were updated
            assert orchestrator.metrics_collector.increment_counter.call_count >= len(orchestrator.backup_tiers)

    @pytest.mark.asyncio
    async def test_get_backup_status_specific_job(self, orchestrator):
        """Test getting status for specific backup job."""
        # Add a job to history
        result = BackupResult(
            job_id="status-test",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(minutes=10),
            status=BackupStatus.COMPLETED,
            components={"database": True},
            backup_paths=["/backup/db.sql"],
            size_bytes=1000000,
            checksum="status123",
            coppa_verified=True
        )
        orchestrator.job_history.append(result)
        
        status = await orchestrator.get_backup_status("status-test")
        
        assert status["job_id"] == "status-test"
        assert status["status"] == "completed"
        assert status["size_bytes"] == 1000000
        assert status["coppa_verified"] is True

    @pytest.mark.asyncio
    async def test_get_backup_status_job_not_found(self, orchestrator):
        """Test getting status for non-existent job."""
        status = await orchestrator.get_backup_status("nonexistent")
        
        assert "error" in status
        assert "not found" in status["error"]

    @pytest.mark.asyncio
    async def test_get_backup_status_all_jobs(self, orchestrator):
        """Test getting status for all jobs."""
        # Add some jobs to history
        completed_result = BackupResult(
            job_id="completed-1",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(minutes=10),
            status=BackupStatus.COMPLETED,
            components={"database": True},
            backup_paths=["/backup/db1.sql"],
            size_bytes=1000000,
            checksum="comp123"
        )
        
        failed_result = BackupResult(
            job_id="failed-1",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(minutes=5),
            status=BackupStatus.FAILED,
            components={"database": False},
            backup_paths=[],
            size_bytes=0,
            checksum="",
            error_message="Test failure"
        )
        
        orchestrator.job_history.extend([completed_result, failed_result])
        orchestrator.active_jobs["active-1"] = Mock()
        
        status = await orchestrator.get_backup_status()
        
        assert status["active_jobs"] == 1
        assert status["completed_jobs"] == 1
        assert status["failed_jobs"] == 1
        assert status["total_size_bytes"] == 1000000
        assert len(status["recent_jobs"]) == 2

    @pytest.mark.asyncio
    async def test_start_scheduler(self, orchestrator):
        """Test starting the backup scheduler."""
        with patch.object(orchestrator, 'schedule_backup', new_callable=AsyncMock) as mock_schedule:
            with patch('asyncio.create_task') as mock_create_task:
                await orchestrator.start_scheduler()
                
                # Should schedule all default tiers
                assert mock_schedule.call_count == len(orchestrator.backup_tiers)
                
                # Should start cleanup task
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, orchestrator):
        """Test stopping the backup scheduler."""
        # Add mock active jobs
        mock_task1 = Mock()
        mock_task2 = Mock()
        orchestrator.active_jobs = {
            "job1": mock_task1,
            "job2": mock_task2
        }
        
        with patch('asyncio.gather', new_callable=AsyncMock) as mock_gather:
            await orchestrator.stop_scheduler()
            
            # Should cancel all active jobs
            mock_task1.cancel.assert_called_once()
            mock_task2.cancel.assert_called_once()
            
            # Should wait for cancellation
            mock_gather.assert_called_once()
            
            # Should clear active jobs
            assert len(orchestrator.active_jobs) == 0


class TestBackupTierEnum:
    """Test backup tier enumeration."""

    def test_backup_tier_values(self):
        """Test backup tier enum values."""
        assert BackupTier.HOURLY.value == "hourly"
        assert BackupTier.DAILY.value == "daily"
        assert BackupTier.WEEKLY.value == "weekly"
        assert BackupTier.MONTHLY.value == "monthly"
        assert BackupTier.YEARLY.value == "yearly"


class TestBackupStatusEnum:
    """Test backup status enumeration."""

    def test_backup_status_values(self):
        """Test backup status enum values."""
        assert BackupStatus.PENDING.value == "pending"
        assert BackupStatus.IN_PROGRESS.value == "in_progress"
        assert BackupStatus.COMPLETED.value == "completed"
        assert BackupStatus.FAILED.value == "failed"
        assert BackupStatus.VERIFIED.value == "verified"
        assert BackupStatus.CORRUPTED.value == "corrupted"


class TestBackupOrchestratorIntegration:
    """Test backup orchestrator integration scenarios."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with real-like mock services."""
        database_service = AsyncMock()
        file_service = AsyncMock()
        config_service = AsyncMock()
        monitoring_service = AsyncMock()
        metrics_collector = Mock()
        
        return BackupOrchestrator(
            database_service=database_service,
            file_service=file_service,
            config_service=config_service,
            monitoring_service=monitoring_service,
            metrics_collector=metrics_collector
        )

    @pytest.mark.asyncio
    async def test_full_backup_workflow(self, orchestrator):
        """Test complete backup workflow from scheduling to completion."""
        # Setup mock component results
        db_result = Mock()
        db_result.success = True
        db_result.paths = ["/backup/database.enc"]
        db_result.size_bytes = 1000000
        
        file_result = Mock()
        file_result.success = True
        file_result.paths = ["/backup/files.enc"]
        file_result.size_bytes = 2000000
        
        orchestrator.database_service.create_backup.return_value = db_result
        orchestrator.file_service.create_backup.return_value = file_result
        
        # Create backup job
        job = BackupJob(
            id="integration-test",
            tier=BackupTier.DAILY,
            components=["database", "files"],
            schedule_cron="0 2 * * *",
            retention_days=30,
            coppa_compliance=True
        )
        
        # Mock file operations for integrity verification
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as temp1:
            temp1.write(b"database backup content")
            db_path = temp1.name
            
        with tempfile.NamedTemporaryFile(delete=False) as temp2:
            temp2.write(b"files backup content")
            files_path = temp2.name
        
        try:
            # Update mock results with real file paths
            db_result.paths = [db_path]
            file_result.paths = [files_path]
            
            # Execute the backup
            result = await orchestrator._execute_backup_job(job)
            
            # Verify successful completion
            assert result.status == BackupStatus.VERIFIED
            assert result.components["database"] is True
            assert result.components["files"] is True
            assert result.size_bytes == 3000000
            assert result.checksum != ""
            assert result.coppa_verified is True
            
            # Verify services were called
            orchestrator.database_service.create_backup.assert_called_once()
            orchestrator.file_service.create_backup.assert_called_once()
            orchestrator.monitoring_service.send_backup_notification.assert_called_once()
            
        finally:
            # Cleanup temp files
            import os
            os.unlink(db_path)
            os.unlink(files_path)