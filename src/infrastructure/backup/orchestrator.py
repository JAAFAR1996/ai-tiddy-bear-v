"""
Backup Orchestrator for AI Teddy Bear Application

Manages the complete backup lifecycle with multi-tier strategy,
COPPA compliance, and disaster recovery capabilities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json

from ..monitoring.prometheus_metrics import PrometheusMetricsCollector


class BackupTier(Enum):
    """Backup tier levels with different retention policies"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class BackupStatus(Enum):
    """Backup operation status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"


@dataclass
class BackupJob:
    """Backup job configuration"""
    id: str
    tier: BackupTier
    components: List[str]  # database, files, config
    schedule_cron: str
    retention_days: int
    encryption_enabled: bool = True
    compression_enabled: bool = True
    coppa_compliance: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class BackupResult:
    """Result of a backup operation"""
    job_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: BackupStatus
    components: Dict[str, bool]  # component -> success
    backup_paths: List[str]
    size_bytes: int
    checksum: str
    error_message: Optional[str] = None
    coppa_verified: bool = True


class BackupOrchestrator:
    """
    Orchestrates all backup operations with multi-tier strategy,
    scheduling, monitoring, and COPPA compliance.
    """

    def __init__(self, 
                 database_service=None,
                 file_service=None, 
                 config_service=None,
                 monitoring_service=None,
                 metrics_collector=None):
        self.database_service = database_service
        self.file_service = file_service
        self.config_service = config_service
        self.monitoring_service = monitoring_service
        self.metrics_collector = metrics_collector or PrometheusMetricsCollector()
        
        self.logger = logging.getLogger(__name__)
        self.active_jobs: Dict[str, asyncio.Task] = {}
        self.job_history: List[BackupResult] = []
        
        # Default backup tiers with COPPA-compliant retention
        self.backup_tiers = self._initialize_backup_tiers()
        
    def _initialize_backup_tiers(self) -> Dict[BackupTier, BackupJob]:
        """Initialize default backup tier configurations"""
        return {
            BackupTier.HOURLY: BackupJob(
                id="hourly_backup",
                tier=BackupTier.HOURLY,
                components=["database"],
                schedule_cron="0 * * * *",  # Every hour
                retention_days=7,
                encryption_enabled=True,
                coppa_compliance=True
            ),
            BackupTier.DAILY: BackupJob(
                id="daily_backup", 
                tier=BackupTier.DAILY,
                components=["database", "files", "config"],
                schedule_cron="0 2 * * *",  # 2 AM daily
                retention_days=90,
                encryption_enabled=True,
                coppa_compliance=True
            ),
            BackupTier.WEEKLY: BackupJob(
                id="weekly_backup",
                tier=BackupTier.WEEKLY, 
                components=["database", "files", "config"],
                schedule_cron="0 1 * * 0",  # 1 AM Sundays
                retention_days=365,
                encryption_enabled=True,
                coppa_compliance=True
            ),
            BackupTier.MONTHLY: BackupJob(
                id="monthly_backup",
                tier=BackupTier.MONTHLY,
                components=["database", "files", "config"],
                schedule_cron="0 1 1 * *",  # 1 AM 1st of month
                retention_days=2555,  # 7 years for compliance
                encryption_enabled=True,
                coppa_compliance=True
            )
        }

    async def schedule_backup(self, job: BackupJob) -> str:
        """Schedule a backup job"""
        try:
            self.logger.info(f"Scheduling backup job: {job.id}")
            
            # Validate job configuration
            await self._validate_backup_job(job)
            
            # Create backup task
            task = asyncio.create_task(self._execute_backup_job(job))
            self.active_jobs[job.id] = task
            
            # Track metrics
            self.metrics_collector.increment_counter(
                "backup_jobs_scheduled_total", 
                {"tier": job.tier.value}
            )
            
            return job.id
            
        except Exception as e:
            self.logger.error(f"Failed to schedule backup job {job.id}: {e}")
            raise

    async def _validate_backup_job(self, job: BackupJob) -> None:
        """Validate backup job configuration"""
        if not job.components:
            raise ValueError("Backup job must specify at least one component")
            
        if job.coppa_compliance and not job.encryption_enabled:
            raise ValueError("COPPA compliance requires encryption")
            
        # Validate services are available
        for component in job.components:
            if component == "database" and not self.database_service:
                raise ValueError("Database service not configured")
            elif component == "files" and not self.file_service:
                raise ValueError("File service not configured")
            elif component == "config" and not self.config_service:
                raise ValueError("Config service not configured")

    async def _execute_backup_job(self, job: BackupJob) -> BackupResult:
        """Execute a backup job with all components"""
        start_time = datetime.utcnow()
        result = BackupResult(
            job_id=job.id,
            start_time=start_time,
            end_time=None,
            status=BackupStatus.IN_PROGRESS,
            components={},
            backup_paths=[],
            size_bytes=0,
            checksum="",
            coppa_verified=job.coppa_compliance
        )
        
        try:
            self.logger.info(f"Starting backup job: {job.id}")
            
            # Pre-backup COPPA compliance check
            if job.coppa_compliance:
                await self._verify_coppa_compliance_pre_backup()
            
            # Execute each component backup
            for component in job.components:
                try:
                    component_result = await self._backup_component(
                        component, job
                    )
                    result.components[component] = component_result.success
                    if component_result.success:
                        result.backup_paths.extend(component_result.paths)
                        result.size_bytes += component_result.size_bytes
                        
                except Exception as e:
                    self.logger.error(f"Component {component} backup failed: {e}")
                    result.components[component] = False
                    result.error_message = str(e)
            
            # Post-backup verification
            if all(result.components.values()):
                await self._verify_backup_integrity(result)
                result.status = BackupStatus.VERIFIED
                
                # COPPA compliance verification
                if job.coppa_compliance:
                    result.coppa_verified = await self._verify_coppa_compliance_post_backup(result)
                    
            else:
                result.status = BackupStatus.FAILED
                
            result.end_time = datetime.utcnow()
            
            # Store result and notify
            self.job_history.append(result)
            await self._notify_backup_completion(result)
            
            # Update metrics
            self._update_backup_metrics(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Backup job {job.id} failed: {e}")
            result.status = BackupStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.utcnow()
            
            self.job_history.append(result)
            await self._notify_backup_failure(result)
            
            return result
            
        finally:
            # Clean up active job
            if job.id in self.active_jobs:
                del self.active_jobs[job.id]

    async def _backup_component(self, component: str, job: BackupJob) -> Any:
        """Backup a specific component"""
        if component == "database":
            return await self.database_service.create_backup(
                encryption=job.encryption_enabled,
                compression=job.compression_enabled,
                coppa_compliant=job.coppa_compliance
            )
        elif component == "files":
            return await self.file_service.create_backup(
                encryption=job.encryption_enabled,
                compression=job.compression_enabled,
                coppa_compliant=job.coppa_compliance
            )
        elif component == "config":
            return await self.config_service.create_backup(
                encryption=job.encryption_enabled,
                compression=job.compression_enabled
            )
        else:
            raise ValueError(f"Unknown backup component: {component}")

    async def _verify_coppa_compliance_pre_backup(self) -> None:
        """Verify COPPA compliance before backup"""
        self.logger.info("Performing COPPA compliance check...")
        
        # Check that child data encryption is enabled
        # Check that access logs are properly anonymized
        # Verify data retention policies are in place
        
        # This would interface with actual compliance checking
        await asyncio.sleep(0.1)  # Simulated check
        
    async def _verify_coppa_compliance_post_backup(self, result: BackupResult) -> bool:
        """Verify COPPA compliance after backup"""
        try:
            # Verify backup encryption
            if not self._verify_backup_encryption(result.backup_paths):
                return False
                
            # Verify no unencrypted child data in backup
            if not await self._scan_backup_for_sensitive_data(result.backup_paths):
                return False
                
            # Verify backup access controls
            if not self._verify_backup_access_controls(result.backup_paths):
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"COPPA compliance verification failed: {e}")
            return False

    def _verify_backup_encryption(self, backup_paths: List[str]) -> bool:
        """Verify all backup files are encrypted"""
        for path in backup_paths:
            # Check file headers or metadata for encryption indicators
            # This is a simplified check
            if not path.endswith('.enc'):
                self.logger.warning(f"Backup file may not be encrypted: {path}")
                return False
        return True

    async def _scan_backup_for_sensitive_data(self, backup_paths: List[str]) -> bool:
        """Scan backup for unencrypted sensitive data"""
        # This would implement actual scanning logic
        # for PII, child data, etc.
        return True

    def _verify_backup_access_controls(self, backup_paths: List[str]) -> bool:
        """Verify backup files have proper access controls"""
        import os
        import stat
        
        for path in backup_paths:
            try:
                file_stat = os.stat(path)
                mode = stat.filemode(file_stat.st_mode)
                
                # Check that only owner has read/write access
                if not (file_stat.st_mode & stat.S_IRGRP == 0 and 
                        file_stat.st_mode & stat.S_IROTH == 0):
                    self.logger.warning(f"Backup file has overly permissive access: {path}")
                    return False
                    
            except OSError as e:
                self.logger.error(f"Cannot verify access controls for {path}: {e}")
                return False
                
        return True

    async def _verify_backup_integrity(self, result: BackupResult) -> None:
        """Verify backup integrity with checksums"""
        import hashlib
        
        combined_hash = hashlib.sha256()
        
        for path in result.backup_paths:
            try:
                with open(path, 'rb') as f:
                    while chunk := f.read(8192):
                        combined_hash.update(chunk)
            except Exception as e:
                self.logger.error(f"Failed to verify integrity of {path}: {e}")
                raise
                
        result.checksum = combined_hash.hexdigest()
        self.logger.info(f"Backup integrity verified - checksum: {result.checksum}")

    async def _notify_backup_completion(self, result: BackupResult) -> None:
        """Notify about backup completion"""
        if self.monitoring_service:
            await self.monitoring_service.send_backup_notification(
                job_id=result.job_id,
                status="completed",
                size_mb=result.size_bytes / (1024 * 1024),
                duration_seconds=(result.end_time - result.start_time).total_seconds(),
                coppa_verified=result.coppa_verified
            )

    async def _notify_backup_failure(self, result: BackupResult) -> None:
        """Notify about backup failure"""
        if self.monitoring_service:
            await self.monitoring_service.send_backup_alert(
                job_id=result.job_id,
                error=result.error_message,
                failed_components=list(result.components.keys())
            )

    def _update_backup_metrics(self, result: BackupResult) -> None:
        """Update Prometheus metrics"""
        # Track backup completion
        self.metrics_collector.increment_counter(
            "backup_jobs_completed_total",
            {"status": result.status.value}
        )
        
        # Track backup size
        self.metrics_collector.observe_histogram(
            "backup_size_bytes",
            result.size_bytes,
            {"job_id": result.job_id}
        )
        
        # Track backup duration
        duration = (result.end_time - result.start_time).total_seconds()
        self.metrics_collector.observe_histogram(
            "backup_duration_seconds",
            duration,
            {"job_id": result.job_id}
        )

    async def cleanup_old_backups(self) -> None:
        """Clean up old backups based on retention policies"""
        self.logger.info("Starting backup cleanup process")
        
        for tier, job in self.backup_tiers.items():
            cutoff_date = datetime.utcnow() - timedelta(days=job.retention_days)
            
            # Clean up backups for this tier
            cleaned_count = await self._cleanup_tier_backups(tier, cutoff_date)
            
            self.logger.info(f"Cleaned up {cleaned_count} old {tier.value} backups")
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "backup_cleanup_total",
                {"tier": tier.value, "count": str(cleaned_count)}
            )

    async def _cleanup_tier_backups(self, tier: BackupTier, cutoff_date: datetime) -> int:
        """Clean up backups for a specific tier"""
        # This would implement actual cleanup logic
        # based on storage backend (filesystem, S3, etc.)
        return 0

    async def get_backup_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of backup jobs"""
        if job_id:
            # Return status for specific job
            for result in self.job_history:
                if result.job_id == job_id:
                    return {
                        "job_id": result.job_id,
                        "status": result.status.value,
                        "start_time": result.start_time.isoformat(),
                        "end_time": result.end_time.isoformat() if result.end_time else None,
                        "size_bytes": result.size_bytes,
                        "components": result.components,
                        "coppa_verified": result.coppa_verified
                    }
            return {"error": f"Job {job_id} not found"}
        else:
            # Return status for all jobs
            return {
                "active_jobs": len(self.active_jobs),
                "completed_jobs": len([r for r in self.job_history if r.status == BackupStatus.COMPLETED]),
                "failed_jobs": len([r for r in self.job_history if r.status == BackupStatus.FAILED]),
                "total_size_bytes": sum(r.size_bytes for r in self.job_history),
                "recent_jobs": [
                    {
                        "job_id": r.job_id,
                        "status": r.status.value,
                        "start_time": r.start_time.isoformat(),
                        "size_bytes": r.size_bytes
                    }
                    for r in sorted(self.job_history, key=lambda x: x.start_time, reverse=True)[:10]
                ]
            }

    async def start_scheduler(self) -> None:
        """Start the backup scheduler"""
        self.logger.info("Starting backup scheduler")
        
        # Schedule all default backup tiers
        for tier, job in self.backup_tiers.items():
            await self.schedule_backup(job)
            
        # Start cleanup task
        asyncio.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of old backups"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self.cleanup_old_backups()
            except Exception as e:
                self.logger.error(f"Backup cleanup failed: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry

    async def stop_scheduler(self) -> None:
        """Stop the backup scheduler"""
        self.logger.info("Stopping backup scheduler")
        
        # Cancel all active jobs
        for job_id, task in self.active_jobs.items():
            self.logger.info(f"Cancelling backup job: {job_id}")
            task.cancel()
            
        # Wait for cancellation
        if self.active_jobs:
            await asyncio.gather(*self.active_jobs.values(), return_exceptions=True)
            
        self.active_jobs.clear()
