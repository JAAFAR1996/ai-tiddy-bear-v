#!/usr/bin/env python3
"""
Backup Scheduler Service for AI Teddy Bear Application

Handles scheduled backup operations with:
- Cron-based scheduling
- Queue management
- Load balancing
- Error handling and retries
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import signal
import json

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.infrastructure.backup.orchestrator import (
    BackupOrchestrator, BackupJob, BackupTier, BackupStatus
)
from src.infrastructure.backup.database_backup import DatabaseBackupService
from src.infrastructure.backup.file_backup import FileBackupService, StorageProvider
from src.infrastructure.backup.config_backup import ConfigBackupService
from src.infrastructure.monitoring.prometheus_metrics import PrometheusMetricsCollector


class BackupScheduler:
    """
    Backup scheduler service that manages timed backup operations
    """

    def __init__(self):
        self.logger = self._setup_logging()
        self.running = False
        self.check_interval = int(os.getenv('SCHEDULER_CHECK_INTERVAL_SECONDS', '60'))
        
        # Initialize services
        self.orchestrator = self._initialize_orchestrator()
        self.scheduled_jobs: Dict[str, BackupJob] = {}
        
        # Metrics
        self.metrics_collector = PrometheusMetricsCollector()
        
        # Job queue
        self.job_queue: List[BackupJob] = []
        self.max_concurrent_jobs = int(os.getenv('BACKUP_PARALLEL_JOBS', '2'))
        self.active_jobs: Dict[str, asyncio.Task] = {}

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def _initialize_orchestrator(self) -> BackupOrchestrator:
        """Initialize backup orchestrator"""
        # Database service
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        database_service = DatabaseBackupService(
            database_url=database_url,
            backup_base_path='/app/backups/database',
            encryption_key=os.getenv('BACKUP_ENCRYPTION_KEY')
        )
        
        # File service with storage backends
        storage_backends = {}
        
        # Local storage (always available)
        from src.infrastructure.backup.file_backup import LocalBackend
        storage_backends[StorageProvider.LOCAL] = LocalBackend('/app/backups/files')
        
        # AWS S3 (if configured)
        if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
            from src.infrastructure.backup.file_backup import S3Backend
            storage_backends[StorageProvider.S3] = S3Backend(
                bucket_name=os.getenv('S3_BACKUP_BUCKET', 'ai-teddy-backups'),
                access_key=os.getenv('AWS_ACCESS_KEY_ID'),
                secret_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            )
        
        # Azure (if configured)
        if os.getenv('AZURE_STORAGE_CONNECTION_STRING'):
            from src.infrastructure.backup.file_backup import AzureBackend
            storage_backends[StorageProvider.AZURE] = AzureBackend(
                container_name=os.getenv('AZURE_BACKUP_CONTAINER', 'backups'),
                connection_string=os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            )
        
        file_service = FileBackupService(
            backup_base_path='/app/backups/files',
            storage_backends=storage_backends,
            encryption_key=os.getenv('BACKUP_ENCRYPTION_KEY')
        )
        
        # Config service
        config_service = ConfigBackupService(
            backup_base_path='/app/backups/config',
            encryption_key=os.getenv('BACKUP_ENCRYPTION_KEY')
        )
        
        return BackupOrchestrator(
            database_service=database_service,
            file_service=file_service,
            config_service=config_service,
            metrics_collector=self.metrics_collector
        )

    def _initialize_scheduled_jobs(self) -> None:
        """Initialize default scheduled backup jobs"""
        jobs = {}
        
        # Hourly database backups
        if os.getenv('HOURLY_BACKUP_ENABLED', 'true').lower() == 'true':
            jobs['hourly_db'] = BackupJob(
                id='hourly_db_backup',
                tier=BackupTier.HOURLY,
                components=['database'],
                schedule_cron='0 * * * *',  # Every hour
                retention_days=7,
                encryption_enabled=True,
                coppa_compliance=True
            )
        
        # Daily full backups
        if os.getenv('DAILY_BACKUP_ENABLED', 'true').lower() == 'true':
            jobs['daily_full'] = BackupJob(
                id='daily_full_backup',
                tier=BackupTier.DAILY,
                components=['database', 'files', 'config'],
                schedule_cron='0 2 * * *',  # 2 AM daily
                retention_days=30,
                encryption_enabled=True,
                coppa_compliance=True
            )
        
        # Weekly comprehensive backups
        if os.getenv('WEEKLY_BACKUP_ENABLED', 'true').lower() == 'true':
            jobs['weekly_comprehensive'] = BackupJob(
                id='weekly_comprehensive_backup',
                tier=BackupTier.WEEKLY,
                components=['database', 'files', 'config'],
                schedule_cron='0 1 * * 0',  # 1 AM Sundays
                retention_days=90,
                encryption_enabled=True,
                coppa_compliance=True,
                metadata={'type': 'comprehensive', 'verification': True}
            )
        
        # Monthly archive backups
        if os.getenv('MONTHLY_BACKUP_ENABLED', 'true').lower() == 'true':
            jobs['monthly_archive'] = BackupJob(
                id='monthly_archive_backup',
                tier=BackupTier.MONTHLY,
                components=['database', 'files', 'config'],
                schedule_cron='0 1 1 * *',  # 1 AM 1st of month
                retention_days=2555,  # 7 years
                encryption_enabled=True,
                coppa_compliance=True,
                metadata={'type': 'archive', 'long_term_retention': True}
            )
        
        self.scheduled_jobs = jobs
        self.logger.info(f"Initialized {len(jobs)} scheduled backup jobs")

    def _should_run_job(self, job: BackupJob, current_time: datetime) -> bool:
        """Check if a job should run based on its cron schedule"""
        from croniter import croniter
        
        try:
            # Get the last run time (simplified - would store in database)
            last_run_time = current_time - timedelta(hours=1)  # Placeholder
            
            # Check if it's time to run
            cron = croniter(job.schedule_cron, last_run_time)
            next_run = cron.get_next(datetime)
            
            return current_time >= next_run
            
        except Exception as e:
            self.logger.error(f"Error checking schedule for job {job.id}: {e}")
            return False

    async def _execute_backup_job(self, job: BackupJob) -> None:
        """Execute a backup job"""
        try:
            self.logger.info(f"Starting scheduled backup job: {job.id}")
            
            # Execute the backup
            result = await self.orchestrator._execute_backup_job(job)
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "scheduled_backup_jobs_total",
                {
                    "job_id": job.id,
                    "tier": job.tier.value,
                    "status": result.status.value
                }
            )
            
            if result.status == BackupStatus.COMPLETED:
                self.logger.info(f"Scheduled backup job completed: {job.id}")
            else:
                self.logger.error(f"Scheduled backup job failed: {job.id} - {result.error_message}")
                
        except Exception as e:
            self.logger.error(f"Error executing scheduled backup job {job.id}: {e}")
            
            self.metrics_collector.increment_counter(
                "scheduled_backup_job_errors_total",
                {"job_id": job.id, "tier": job.tier.value}
            )

    async def _process_job_queue(self) -> None:
        """Process the job queue with concurrency limits"""
        while self.job_queue and len(self.active_jobs) < self.max_concurrent_jobs:
            job = self.job_queue.pop(0)
            
            # Create task for the job
            task = asyncio.create_task(self._execute_backup_job(job))
            self.active_jobs[job.id] = task
            
            self.logger.info(f"Started backup job: {job.id} (active jobs: {len(self.active_jobs)})")
        
        # Clean up completed tasks
        completed_jobs = []
        for job_id, task in self.active_jobs.items():
            if task.done():
                completed_jobs.append(job_id)
                try:
                    await task  # Get any exceptions
                except Exception as e:
                    self.logger.error(f"Backup job {job_id} failed: {e}")
        
        for job_id in completed_jobs:
            del self.active_jobs[job_id]
            self.logger.info(f"Completed backup job: {job_id}")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        self.logger.info("Starting backup scheduler loop")
        
        while self.running:
            try:
                current_time = datetime.utcnow()
                
                # Check each scheduled job
                for job_id, job in self.scheduled_jobs.items():
                    if self._should_run_job(job, current_time):
                        # Add to queue if not already queued or running
                        if (job.id not in [j.id for j in self.job_queue] and
                            job.id not in self.active_jobs):
                            
                            self.job_queue.append(job)
                            self.logger.info(f"Queued backup job: {job.id}")
                
                # Process the job queue
                await self._process_job_queue()
                
                # Update queue metrics
                self.metrics_collector.set_gauge(
                    "backup_scheduler_queue_size",
                    len(self.job_queue)
                )
                
                self.metrics_collector.set_gauge(
                    "backup_scheduler_active_jobs",
                    len(self.active_jobs)
                )
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def start(self) -> None:
        """Start the backup scheduler"""
        self.logger.info("Starting backup scheduler service")
        
        # Initialize scheduled jobs
        self._initialize_scheduled_jobs()
        
        # Set running flag
        self.running = True
        
        # Start the scheduler loop
        await self._scheduler_loop()

    async def stop(self) -> None:
        """Stop the backup scheduler"""
        self.logger.info("Stopping backup scheduler service")
        
        # Set running flag to False
        self.running = False
        
        # Wait for active jobs to complete (with timeout)
        if self.active_jobs:
            self.logger.info(f"Waiting for {len(self.active_jobs)} active jobs to complete...")
            
            # Wait up to 10 minutes for jobs to complete
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.active_jobs.values(), return_exceptions=True),
                    timeout=600
                )
            except asyncio.TimeoutError:
                self.logger.warning("Timeout waiting for backup jobs to complete")
                
                # Cancel remaining jobs
                for task in self.active_jobs.values():
                    task.cancel()
        
        self.logger.info("Backup scheduler service stopped")

    def add_job(self, job: BackupJob) -> None:
        """Add a new scheduled job"""
        self.scheduled_jobs[job.id] = job
        self.logger.info(f"Added scheduled job: {job.id}")

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        if job_id in self.scheduled_jobs:
            del self.scheduled_jobs[job_id]
            self.logger.info(f"Removed scheduled job: {job_id}")
            return True
        return False

    def get_job_status(self) -> Dict[str, any]:
        """Get current scheduler status"""
        return {
            'running': self.running,
            'scheduled_jobs': len(self.scheduled_jobs),
            'queued_jobs': len(self.job_queue),
            'active_jobs': len(self.active_jobs),
            'max_concurrent_jobs': self.max_concurrent_jobs,
            'check_interval_seconds': self.check_interval,
            'job_details': {
                'scheduled': list(self.scheduled_jobs.keys()),
                'queued': [job.id for job in self.job_queue],
                'active': list(self.active_jobs.keys())
            }
        }


def setup_signal_handlers(scheduler: BackupScheduler) -> None:
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(scheduler.stop())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Main entry point"""
    # Create scheduler
    scheduler = BackupScheduler()
    
    # Setup signal handlers
    setup_signal_handlers(scheduler)
    
    try:
        # Start the scheduler
        await scheduler.start()
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Scheduler failed: {e}")
        return 1
    finally:
        # Ensure clean shutdown
        await scheduler.stop()
    
    return 0


if __name__ == '__main__':
    # Install croniter if not available
    try:
        import croniter
    except ImportError:
        print("Installing croniter...")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'croniter'])
        import croniter
    
    # Run the scheduler
    exit_code = asyncio.run(main())
    sys.exit(exit_code)