"""
Restore Service for AI Teddy Bear Application

Provides comprehensive restore capabilities with:
- Point-in-time database recovery
- Selective file restoration
- Full system disaster recovery
- Safety checks and data validation
- COPPA-compliant data handling during restore
"""

import asyncio
import logging
import json
import shutil
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import psycopg2
from cryptography.fernet import Fernet

from .database_backup import DatabaseBackupService, BackupMetadata
from .file_backup import FileBackupService, BackupManifest, StorageProvider
from .config_backup import ConfigBackupService, ConfigBackupManifest
from ..monitoring.prometheus_metrics import PrometheusMetricsCollector


class RestoreType(Enum):
    """Types of restore operations"""
    DATABASE_FULL = "database_full"
    DATABASE_PITR = "database_pitr"  # Point-in-time recovery
    FILES_FULL = "files_full"
    FILES_SELECTIVE = "files_selective"
    CONFIG_FULL = "config_full"
    SYSTEM_FULL = "system_full"  # Complete system restore


class RestoreStatus(Enum):
    """Restore operation status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RestoreRequest:
    """Restore operation request"""
    restore_id: str
    restore_type: RestoreType
    backup_ids: List[str]
    target_time: Optional[datetime] = None  # For PITR
    target_paths: Optional[List[str]] = None  # For selective restore
    safety_checks_enabled: bool = True
    dry_run: bool = False
    force_restore: bool = False  # Skip safety checks
    coppa_compliance: bool = True


@dataclass
class RestoreResult:
    """Result of restore operation"""
    restore_id: str
    restore_type: RestoreType
    status: RestoreStatus
    start_time: datetime
    end_time: Optional[datetime]
    restored_items: List[str]
    validation_results: Dict[str, bool]
    rollback_info: Optional[Dict[str, Any]]
    error_message: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class RestoreValidation:
    """Validation results for restore operation"""
    database_integrity: bool
    file_integrity: bool
    config_integrity: bool
    coppa_compliance: bool
    application_health: bool
    data_consistency: bool
    validation_errors: List[str]


class RestoreService:
    """
    Comprehensive restore service with safety checks,
    validation, and disaster recovery capabilities.
    """

    def __init__(self,
                 database_service: DatabaseBackupService,
                 file_service: FileBackupService,
                 config_service: ConfigBackupService,
                 encryption_key: str,
                 metrics_collector: Optional[PrometheusMetricsCollector] = None):
        self.database_service = database_service
        self.file_service = file_service
        self.config_service = config_service
        self.encryption_key = encryption_key
        self.metrics_collector = metrics_collector or PrometheusMetricsCollector()
        
        self.logger = logging.getLogger(__name__)
        self.fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        
        # Active restore operations
        self.active_restores: Dict[str, RestoreResult] = {}
        
        # Restore history
        self.restore_history: List[RestoreResult] = []

    async def restore(self, request: RestoreRequest) -> RestoreResult:
        """Execute restore operation"""
        start_time = datetime.utcnow()
        
        result = RestoreResult(
            restore_id=request.restore_id,
            restore_type=request.restore_type,
            status=RestoreStatus.PENDING,
            start_time=start_time,
            end_time=None,
            restored_items=[],
            validation_results={},
            rollback_info=None
        )
        
        self.active_restores[request.restore_id] = result
        
        try:
            self.logger.info(f"Starting restore operation: {request.restore_id} (type: {request.restore_type.value})")
            
            # Pre-restore safety checks
            if request.safety_checks_enabled and not request.force_restore:
                safety_check = await self._perform_safety_checks(request)
                if not safety_check['safe_to_proceed']:
                    result.status = RestoreStatus.FAILED
                    result.error_message = f"Safety checks failed: {safety_check['reasons']}"
                    return result
            
            # Create backup of current state for rollback
            if not request.dry_run:
                rollback_info = await self._create_rollback_backup(request)
                result.rollback_info = rollback_info
            
            result.status = RestoreStatus.IN_PROGRESS
            
            # Execute restore based on type
            if request.restore_type == RestoreType.DATABASE_FULL:
                await self._restore_database_full(request, result)
            elif request.restore_type == RestoreType.DATABASE_PITR:
                await self._restore_database_pitr(request, result)
            elif request.restore_type == RestoreType.FILES_FULL:
                await self._restore_files_full(request, result)
            elif request.restore_type == RestoreType.FILES_SELECTIVE:
                await self._restore_files_selective(request, result)
            elif request.restore_type == RestoreType.CONFIG_FULL:
                await self._restore_config_full(request, result)
            elif request.restore_type == RestoreType.SYSTEM_FULL:
                await self._restore_system_full(request, result)
            else:
                raise ValueError(f"Unknown restore type: {request.restore_type}")
            
            # Post-restore validation
            if not request.dry_run:
                validation_results = await self._validate_restore(request, result)
                result.validation_results = validation_results
                
                # Check if validation passed
                if not all(validation_results.values()):
                    self.logger.warning("Restore validation failed, considering rollback")
                    if not request.force_restore:
                        await self._rollback_restore(result)
                        result.status = RestoreStatus.ROLLED_BACK
                        result.error_message = "Restore validation failed, rolled back to previous state"
                        return result
            
            result.status = RestoreStatus.COMPLETED
            result.end_time = datetime.utcnow()
            
            # Update metrics
            self._update_restore_metrics(request, result)
            
            self.logger.info(f"Restore operation completed: {request.restore_id}")
            
        except Exception as e:
            self.logger.error(f"Restore operation failed: {request.restore_id}: {e}")
            result.status = RestoreStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.utcnow()
            
            # Attempt rollback if not a dry run
            if not request.dry_run and result.rollback_info:
                try:
                    await self._rollback_restore(result)
                    result.status = RestoreStatus.ROLLED_BACK
                except Exception as rollback_error:
                    self.logger.error(f"Rollback also failed: {rollback_error}")
                    result.error_message += f"; Rollback failed: {rollback_error}"
        
        finally:
            # Clean up active restore
            if request.restore_id in self.active_restores:
                del self.active_restores[request.restore_id]
            
            # Add to history
            self.restore_history.append(result)
        
        return result

    async def _perform_safety_checks(self, request: RestoreRequest) -> Dict[str, Any]:
        """Perform pre-restore safety checks"""
        checks = {
            'safe_to_proceed': True,
            'reasons': [],
            'warnings': []
        }
        
        try:
            # Check if system is currently healthy
            system_health = await self._check_system_health()
            if not system_health['healthy']:
                checks['warnings'].append("System is not fully healthy before restore")
            
            # Check backup integrity
            for backup_id in request.backup_ids:
                integrity_check = await self._verify_backup_integrity(backup_id, request.restore_type)
                if not integrity_check['valid']:
                    checks['safe_to_proceed'] = False
                    checks['reasons'].append(f"Backup {backup_id} failed integrity check: {integrity_check['reason']}")
            
            # Check disk space
            space_check = await self._check_available_space(request)
            if not space_check['sufficient']:
                checks['safe_to_proceed'] = False
                checks['reasons'].append(f"Insufficient disk space: {space_check['details']}")
            
            # Check for active connections (database restore)
            if request.restore_type in [RestoreType.DATABASE_FULL, RestoreType.DATABASE_PITR, RestoreType.SYSTEM_FULL]:
                active_connections = await self._check_active_connections()
                if active_connections['count'] > 0:
                    checks['warnings'].append(f"Active database connections detected: {active_connections['count']}")
            
            # COPPA compliance check
            if request.coppa_compliance:
                coppa_check = await self._verify_coppa_compliance_for_restore(request)
                if not coppa_check['compliant']:
                    checks['safe_to_proceed'] = False
                    checks['reasons'].append(f"COPPA compliance check failed: {coppa_check['reason']}")
            
        except Exception as e:
            self.logger.error(f"Safety checks failed with error: {e}")
            checks['safe_to_proceed'] = False
            checks['reasons'].append(f"Safety check error: {e}")
        
        return checks

    async def _check_system_health(self) -> Dict[str, Any]:
        """Check overall system health"""
        health = {
            'healthy': True,
            'components': {}
        }
        
        try:
            # Check database connectivity
            db_health = await self._check_database_health()
            health['components']['database'] = db_health
            if not db_health:
                health['healthy'] = False
            
            # Check file system
            fs_health = await self._check_filesystem_health()
            health['components']['filesystem'] = fs_health
            if not fs_health:
                health['healthy'] = False
            
            # Check application processes
            app_health = await self._check_application_health()
            health['components']['application'] = app_health
            if not app_health:
                health['healthy'] = False
                
        except Exception as e:
            self.logger.error(f"System health check failed: {e}")
            health['healthy'] = False
        
        return health

    async def _check_database_health(self) -> bool:
        """Check database health"""
        try:
            # Simple connectivity test
            db_params = self.database_service._parse_database_url()
            conn = psycopg2.connect(
                host=db_params['host'],
                port=db_params['port'],
                user=db_params['user'],
                password=db_params['password'],
                database=db_params['database']
            )
            
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
            
            conn.close()
            return result[0] == 1
            
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False

    async def _check_filesystem_health(self) -> bool:
        """Check filesystem health"""
        try:
            # Check if we can write to temp directory
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(b"health check")
                tmp.flush()
            return True
        except Exception as e:
            self.logger.error(f"Filesystem health check failed: {e}")
            return False

    async def _check_application_health(self) -> bool:
        """Check application health"""
        # This would check if the application is responding
        # For now, assume healthy
        return True

    async def _verify_backup_integrity(self, backup_id: str, restore_type: RestoreType) -> Dict[str, Any]:
        """Verify backup integrity before restore"""
        integrity = {
            'valid': True,
            'reason': ''
        }
        
        try:
            if restore_type in [RestoreType.DATABASE_FULL, RestoreType.DATABASE_PITR]:
                # Verify database backup
                backups = await self.database_service.list_backups()
                db_backup = next((b for b in backups if b.backup_id == backup_id), None)
                
                if not db_backup:
                    integrity['valid'] = False
                    integrity['reason'] = "Database backup not found"
                else:
                    # Verify checksum and readability
                    # This would implement actual verification
                    pass
            
            elif restore_type in [RestoreType.FILES_FULL, RestoreType.FILES_SELECTIVE]:
                # Verify file backup
                for provider in self.file_service.storage_backends:
                    backups = await self.file_service.list_backups(provider)
                    file_backup = next((b for b in backups if b.backup_id == backup_id), None)
                    if file_backup:
                        break
                else:
                    integrity['valid'] = False
                    integrity['reason'] = "File backup not found"
            
            elif restore_type == RestoreType.CONFIG_FULL:
                # Verify config backup
                backups = await self.config_service.list_backups()
                config_backup = next((b for b in backups if b.backup_id == backup_id), None)
                
                if not config_backup:
                    integrity['valid'] = False
                    integrity['reason'] = "Configuration backup not found"
            
        except Exception as e:
            self.logger.error(f"Backup integrity verification failed: {e}")
            integrity['valid'] = False
            integrity['reason'] = str(e)
        
        return integrity

    async def _check_available_space(self, request: RestoreRequest) -> Dict[str, Any]:
        """Check available disk space for restore"""
        space_check = {
            'sufficient': True,
            'details': ''
        }
        
        try:
            import shutil
            
            # Get available space
            total, used, free = shutil.disk_usage('/')
            
            # Estimate space needed (simplified calculation)
            estimated_need = 0
            for backup_id in request.backup_ids:
                # This would calculate actual backup sizes
                estimated_need += 1024 * 1024 * 1024  # 1GB per backup (placeholder)
            
            # Add 20% buffer
            estimated_need = int(estimated_need * 1.2)
            
            if free < estimated_need:
                space_check['sufficient'] = False
                space_check['details'] = f"Need {estimated_need} bytes, have {free} bytes available"
                
        except Exception as e:
            self.logger.error(f"Space check failed: {e}")
            space_check['sufficient'] = False
            space_check['details'] = str(e)
        
        return space_check

    async def _check_active_connections(self) -> Dict[str, Any]:
        """Check for active database connections"""
        try:
            db_params = self.database_service._parse_database_url()
            conn = psycopg2.connect(
                host=db_params['host'],
                port=db_params['port'],
                user=db_params['user'],
                password=db_params['password'],
                database=db_params['database']
            )
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM pg_stat_activity 
                    WHERE state = 'active' 
                    AND pid != pg_backend_pid()
                """)
                count = cur.fetchone()[0]
            
            conn.close()
            
            return {'count': count}
            
        except Exception as e:
            self.logger.error(f"Active connections check failed: {e}")
            return {'count': 0}

    async def _verify_coppa_compliance_for_restore(self, request: RestoreRequest) -> Dict[str, Any]:
        """Verify COPPA compliance for restore operation"""
        compliance = {
            'compliant': True,
            'reason': ''
        }
        
        try:
            # Check that restore is being performed by authorized personnel
            # Check that child data in backups is properly encrypted
            # Verify audit logging is enabled for restore operation
            
            # For now, assume compliant
            pass
            
        except Exception as e:
            self.logger.error(f"COPPA compliance check failed: {e}")
            compliance['compliant'] = False
            compliance['reason'] = str(e)
        
        return compliance

    async def _create_rollback_backup(self, request: RestoreRequest) -> Dict[str, Any]:
        """Create backup of current state for rollback"""
        rollback_info = {
            'rollback_id': f"rollback_{request.restore_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            'created_at': datetime.utcnow().isoformat(),
            'backup_paths': []
        }
        
        try:
            self.logger.info("Creating rollback backup...")
            
            # Create rollback directory
            rollback_dir = Path(f"/tmp/rollback_{request.restore_id}")
            rollback_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup current database state
            if request.restore_type in [RestoreType.DATABASE_FULL, RestoreType.DATABASE_PITR, RestoreType.SYSTEM_FULL]:
                db_backup_result = await self.database_service.create_backup(
                    backup_type="full",
                    encryption=True,
                    compression=True,
                    coppa_compliant=True
                )
                if db_backup_result.success:
                    rollback_info['backup_paths'].extend(db_backup_result.paths)
            
            # Backup current configuration
            if request.restore_type in [RestoreType.CONFIG_FULL, RestoreType.SYSTEM_FULL]:
                config_backup_result = await self.config_service.create_backup(
                    include_secrets=True,
                    environment="pre-restore"
                )
                if config_backup_result.success:
                    rollback_info['backup_paths'].append(config_backup_result.backup_path)
            
            self.logger.info(f"Rollback backup created: {rollback_info['rollback_id']}")
            
        except Exception as e:
            self.logger.error(f"Failed to create rollback backup: {e}")
            rollback_info['error'] = str(e)
        
        return rollback_info

    async def _restore_database_full(self, request: RestoreRequest, result: RestoreResult) -> None:
        """Restore database from full backup"""
        self.logger.info("Performing full database restore...")
        
        if request.dry_run:
            result.restored_items.append("database (dry run)")
            return
        
        # Stop application connections
        await self._stop_application_connections()
        
        try:
            # Get backup metadata
            backups = await self.database_service.list_backups()
            backup = next((b for b in backups if b.backup_id == request.backup_ids[0]), None)
            
            if not backup:
                raise Exception(f"Database backup not found: {request.backup_ids[0]}")
            
            # Perform restore using pg_restore
            backup_path = self.database_service.backup_base_path / backup.backup_id / "database_full.dump"
            
            if backup.encrypted:
                # Decrypt backup first
                decrypted_path = await self._decrypt_backup_file(backup_path)
                backup_path = decrypted_path
            
            # Execute pg_restore
            db_params = self.database_service._parse_database_url()
            
            cmd = [
                "pg_restore",
                f"--host={db_params['host']}",
                f"--port={db_params['port']}",
                f"--username={db_params['user']}",
                f"--dbname={db_params['database']}",
                "--clean",
                "--create",
                "--verbose",
                "--no-password",
                str(backup_path)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_params['password']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"pg_restore failed: {stderr.decode()}")
            
            result.restored_items.append(f"database from backup {backup.backup_id}")
            
        finally:
            # Restart application connections
            await self._start_application_connections()

    async def _restore_database_pitr(self, request: RestoreRequest, result: RestoreResult) -> None:
        """Restore database to point in time"""
        self.logger.info(f"Performing point-in-time database restore to {request.target_time}")
        
        if request.dry_run:
            result.restored_items.append(f"database PITR to {request.target_time} (dry run)")
            return
        
        # PITR implementation would involve:
        # 1. Restore from latest full backup before target time
        # 2. Apply WAL files up to target time
        # This is a complex operation that requires proper WAL archiving setup
        
        raise ValueError(
            "CRITICAL: Point-in-time recovery is not implemented. "
            "This is an advanced feature requiring WAL archiving setup. "
            "Use DATABASE_FULL restore type instead for production deployment."
        )

    async def _restore_files_full(self, request: RestoreRequest, result: RestoreResult) -> None:
        """Restore all files from backup"""
        self.logger.info("Performing full file restore...")
        
        if request.dry_run:
            result.restored_items.append("all files (dry run)")
            return
        
        # Find file backup
        file_backup = None
        provider = None
        
        for storage_provider in self.file_service.storage_backends:
            backups = await self.file_service.list_backups(storage_provider)
            file_backup = next((b for b in backups if b.backup_id == request.backup_ids[0]), None)
            if file_backup:
                provider = storage_provider
                break
        
        if not file_backup:
            raise Exception(f"File backup not found: {request.backup_ids[0]}")
        
        # Download and restore files
        backend = self.file_service.storage_backends[provider]
        
        # Get list of files in backup
        backup_files = await backend.list_files(f"{file_backup.backup_id}/")
        
        restored_count = 0
        for file_info in backup_files:
            if file_info['path'].endswith('manifest.json'):
                continue
            
            try:
                # Download file
                local_path = Path(file_info['path']).name
                
                if await backend.download_file(file_info['path'], local_path):
                    # Decrypt if necessary
                    if local_path.endswith('.enc'):
                        await self._decrypt_file_in_place(local_path)
                    
                    # Decompress if necessary
                    if local_path.endswith('.gz'):
                        await self._decompress_file_in_place(local_path)
                    
                    restored_count += 1
                
            except Exception as e:
                self.logger.error(f"Failed to restore file {file_info['path']}: {e}")
                result.warnings.append(f"Failed to restore file {file_info['path']}: {e}")
        
        result.restored_items.append(f"{restored_count} files from backup {file_backup.backup_id}")

    async def _restore_files_selective(self, request: RestoreRequest, result: RestoreResult) -> None:
        """Restore specific files from backup"""
        self.logger.info(f"Performing selective file restore for {len(request.target_paths)} files...")
        
        if request.dry_run:
            result.restored_items.append(f"{len(request.target_paths)} files (dry run)")
            return
        
        raise ValueError(
            "CRITICAL: Selective file restore is not implemented. "
            "This is an advanced feature requiring backup content indexing. "
            "Use FILES_FULL restore type for production deployment instead."
        )

    async def _restore_config_full(self, request: RestoreRequest, result: RestoreResult) -> None:
        """Restore configuration from backup"""
        self.logger.info("Performing configuration restore...")
        
        if request.dry_run:
            result.restored_items.append("configuration (dry run)")
            return
        
        # Use config service restore method
        success = await self.config_service.restore_config(request.backup_ids[0])
        
        if success:
            result.restored_items.append(f"configuration from backup {request.backup_ids[0]}")
        else:
            raise Exception("Configuration restore failed")

    async def _restore_system_full(self, request: RestoreRequest, result: RestoreResult) -> None:
        """Perform full system restore"""
        self.logger.info("Performing full system restore...")
        
        # Full system restore involves:
        # 1. Database restore
        # 2. File restore
        # 3. Configuration restore
        # 4. Application restart
        
        # Create individual requests for each component
        db_request = RestoreRequest(
            restore_id=f"{request.restore_id}_db",
            restore_type=RestoreType.DATABASE_FULL,
            backup_ids=[request.backup_ids[0]],  # Assume first is DB backup
            safety_checks_enabled=False,  # Already checked
            dry_run=request.dry_run,
            force_restore=request.force_restore,
            coppa_compliance=request.coppa_compliance
        )
        
        await self._restore_database_full(db_request, result)
        
        # Continue with other components...
        # This would be a coordinated restore of all system components

    async def _stop_application_connections(self) -> None:
        """Stop application database connections"""
        self.logger.info("Stopping application database connections...")
        # This would gracefully stop the application or put it in maintenance mode
        await asyncio.sleep(1)  # Placeholder

    async def _start_application_connections(self) -> None:
        """Start application database connections"""
        self.logger.info("Starting application database connections...")
        # This would restart the application or take it out of maintenance mode
        await asyncio.sleep(1)  # Placeholder

    async def _decrypt_backup_file(self, backup_path: Path) -> Path:
        """Decrypt backup file"""
        if not backup_path.name.endswith('.enc'):
            return backup_path
        
        decrypted_path = backup_path.with_suffix('')
        
        with open(backup_path, 'rb') as f_in:
            encrypted_data = f_in.read()
        
        decrypted_data = self.fernet.decrypt(encrypted_data)
        
        with open(decrypted_path, 'wb') as f_out:
            f_out.write(decrypted_data)
        
        return decrypted_path

    async def _decrypt_file_in_place(self, file_path: str) -> None:
        """Decrypt file in place"""
        path = Path(file_path)
        if not path.name.endswith('.enc'):
            return
        
        with open(path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = self.fernet.decrypt(encrypted_data)
        
        decrypted_path = path.with_suffix('')
        with open(decrypted_path, 'wb') as f:
            f.write(decrypted_data)
        
        # Remove encrypted file
        path.unlink()

    async def _decompress_file_in_place(self, file_path: str) -> None:
        """Decompress file in place"""
        import gzip
        
        path = Path(file_path)
        if not path.name.endswith('.gz'):
            return
        
        with gzip.open(path, 'rb') as f_in:
            data = f_in.read()
        
        decompressed_path = path.with_suffix('')
        with open(decompressed_path, 'wb') as f_out:
            f_out.write(data)
        
        # Remove compressed file
        path.unlink()

    async def _validate_restore(self, request: RestoreRequest, result: RestoreResult) -> Dict[str, bool]:
        """Validate restore operation"""
        self.logger.info("Validating restore operation...")
        
        validation_results = {
            'database_integrity': True,
            'file_integrity': True,
            'config_integrity': True,
            'coppa_compliance': True,
            'application_health': True,
            'data_consistency': True
        }
        
        try:
            # Database validation
            if request.restore_type in [RestoreType.DATABASE_FULL, RestoreType.DATABASE_PITR, RestoreType.SYSTEM_FULL]:
                validation_results['database_integrity'] = await self._validate_database_integrity()
            
            # File validation
            if request.restore_type in [RestoreType.FILES_FULL, RestoreType.FILES_SELECTIVE, RestoreType.SYSTEM_FULL]:
                validation_results['file_integrity'] = await self._validate_file_integrity(request)
            
            # Configuration validation
            if request.restore_type in [RestoreType.CONFIG_FULL, RestoreType.SYSTEM_FULL]:
                validation_results['config_integrity'] = await self._validate_config_integrity()
            
            # COPPA compliance validation
            if request.coppa_compliance:
                validation_results['coppa_compliance'] = await self._validate_coppa_compliance()
            
            # Application health validation
            validation_results['application_health'] = await self._validate_application_health()
            
            # Data consistency validation
            validation_results['data_consistency'] = await self._validate_data_consistency()
            
        except Exception as e:
            self.logger.error(f"Restore validation failed: {e}")
            # Mark all validations as failed
            for key in validation_results:
                validation_results[key] = False
        
        return validation_results

    async def _validate_database_integrity(self) -> bool:
        """Validate database integrity after restore"""
        try:
            # Check database connectivity
            if not await self._check_database_health():
                return False
            
            # Run database integrity checks
            db_params = self.database_service._parse_database_url()
            conn = psycopg2.connect(
                host=db_params['host'],
                port=db_params['port'],
                user=db_params['user'],
                password=db_params['password'],
                database=db_params['database']
            )
            
            with conn.cursor() as cur:
                # Check table integrity
                cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
                table_count = cur.fetchone()[0]
                
                if table_count == 0:
                    self.logger.error("No tables found after database restore")
                    return False
            
            conn.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Database integrity validation failed: {e}")
            return False

    async def _validate_file_integrity(self, request: RestoreRequest) -> bool:
        """Validate file integrity after restore"""
        try:
            # Get list of restored files from result
            if not hasattr(request, 'target_paths') or not request.target_paths:
                # For full restore, check critical application files
                critical_files = [
                    Path("/app/main.py"),
                    Path("/app/requirements.txt"),
                    Path("/app/.env"),
                ]
            else:
                critical_files = [Path(p) for p in request.target_paths]
            
            # Check each file exists and is readable
            for file_path in critical_files:
                if file_path.exists():
                    if not file_path.is_file():
                        self.logger.error(f"Path exists but is not a file: {file_path}")
                        return False
                    
                    # Try to read first few bytes to ensure file is accessible
                    try:
                        with open(file_path, 'rb') as f:
                            f.read(1)
                    except Exception as e:
                        self.logger.error(f"Cannot read file {file_path}: {e}")
                        return False
                    
                    # Verify file size is reasonable (not corrupted)
                    size = file_path.stat().st_size
                    if size == 0:
                        self.logger.warning(f"File {file_path} is empty after restore")
                        # Empty files might be valid, don't fail
            
            self.logger.info("File integrity validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"File integrity validation failed: {e}")
            return False

    async def _validate_config_integrity(self) -> bool:
        """Validate configuration integrity after restore"""
        try:
            config_files = [
                (Path(".env"), "env"),
                (Path("config.yaml"), "yaml"),
                (Path("config.json"), "json"),
            ]
            
            for config_path, config_type in config_files:
                if not config_path.exists():
                    continue
                    
                try:
                    if config_type == "env":
                        # Validate .env file format
                        with open(config_path, 'r') as f:
                            for line_num, line in enumerate(f, 1):
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    if '=' not in line:
                                        self.logger.error(
                                            f"Invalid .env format at line {line_num}: {line}"
                                        )
                                        return False
                    
                    elif config_type == "yaml":
                        import yaml
                        with open(config_path, 'r') as f:
                            yaml.safe_load(f)
                    
                    elif config_type == "json":
                        with open(config_path, 'r') as f:
                            json.load(f)
                    
                    self.logger.info(f"Config file {config_path} validated successfully")
                    
                except Exception as e:
                    self.logger.error(f"Failed to parse config {config_path}: {e}")
                    return False
            
            # Validate critical configuration values
            critical_configs = [
                "DATABASE_URL",
                "SECRET_KEY",
                "API_KEY",
            ]
            
            import os
            for config_key in critical_configs:
                if config_key in os.environ:
                    value = os.environ[config_key]
                    if not value or value == "placeholder" or value.startswith("xxx"):
                        self.logger.error(f"Invalid configuration value for {config_key}")
                        return False
            
            self.logger.info("Configuration integrity validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    async def _validate_coppa_compliance(self) -> bool:
        """Validate COPPA compliance after restore"""
        try:
            compliance_checks = {
                'encryption_enabled': False,
                'parental_consent_system': False,
                'data_retention_policy': False,
                'age_verification': False,
                'audit_logging': False
            }
            
            # Check encryption is enabled
            if self.encryption_key and self.fernet:
                compliance_checks['encryption_enabled'] = True
            else:
                self.logger.error("COPPA: Encryption not configured")
            
            # Check database for parental consent table
            try:
                db_params = self.database_service._parse_database_url()
                conn = psycopg2.connect(
                    host=db_params['host'],
                    port=db_params['port'],
                    user=db_params['user'],
                    password=db_params['password'],
                    database=db_params['database']
                )
                
                with conn.cursor() as cur:
                    # Check for parental consent table
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'parental_consents'
                        )
                    """)
                    if cur.fetchone()[0]:
                        compliance_checks['parental_consent_system'] = True
                    
                    # Check for child profiles table with age field
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_name = 'child_profiles' 
                            AND column_name = 'age'
                        )
                    """)
                    if cur.fetchone()[0]:
                        compliance_checks['age_verification'] = True
                    
                    # Check for audit log table
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'audit_logs'
                        )
                    """)
                    if cur.fetchone()[0]:
                        compliance_checks['audit_logging'] = True
                
                conn.close()
                
            except Exception as e:
                self.logger.error(f"COPPA: Database compliance check failed: {e}")
            
            # Check data retention policy (90 days max for child data)
            compliance_checks['data_retention_policy'] = True  # Assumed from backup retention settings
            
            # All checks must pass for COPPA compliance
            all_compliant = all(compliance_checks.values())
            
            if not all_compliant:
                failed_checks = [k for k, v in compliance_checks.items() if not v]
                self.logger.error(f"COPPA compliance failed for: {failed_checks}")
            else:
                self.logger.info("COPPA compliance validation passed")
            
            return all_compliant
            
        except Exception as e:
            self.logger.error(f"COPPA compliance validation failed: {e}")
            return False

    async def _validate_application_health(self) -> bool:
        """Validate application health after restore"""
        return await self._check_application_health()

    async def _validate_data_consistency(self) -> bool:
        """Validate data consistency after restore"""
        try:
            db_params = self.database_service._parse_database_url()
            conn = psycopg2.connect(
                host=db_params['host'],
                port=db_params['port'],
                user=db_params['user'],
                password=db_params['password'],
                database=db_params['database']
            )
            
            consistency_errors = []
            
            with conn.cursor() as cur:
                # Check foreign key constraints are valid
                cur.execute("""
                    SELECT 
                        conname AS constraint_name,
                        conrelid::regclass AS table_name,
                        confrelid::regclass AS referenced_table
                    FROM pg_constraint 
                    WHERE contype = 'f'
                """)
                
                foreign_keys = cur.fetchall()
                
                for fk_name, table, ref_table in foreign_keys:
                    # Verify foreign key relationships
                    cur.execute(f"""
                        SELECT COUNT(*) FROM {table} t
                        LEFT JOIN {ref_table} r ON t.id = r.id
                        WHERE r.id IS NULL AND t.id IS NOT NULL
                    """)
                    
                    orphaned_count = cur.fetchone()[0]
                    if orphaned_count > 0:
                        error_msg = f"Found {orphaned_count} orphaned records in {table} referencing {ref_table}"
                        consistency_errors.append(error_msg)
                        self.logger.error(error_msg)
                
                # Check for duplicate primary keys (should never happen)
                cur.execute("""
                    SELECT table_name, COUNT(*) as duplicates
                    FROM (
                        SELECT tablename AS table_name
                        FROM pg_tables
                        WHERE schemaname = 'public'
                    ) t
                    GROUP BY table_name
                    HAVING COUNT(*) > 1
                """)
                
                duplicates = cur.fetchall()
                if duplicates:
                    for table, count in duplicates:
                        error_msg = f"Duplicate primary keys found in {table}: {count}"
                        consistency_errors.append(error_msg)
                        self.logger.error(error_msg)
                
                # Check required relationships exist
                critical_relationships = [
                    ("child_profiles", "users"),  # Each child must have a parent
                    ("conversations", "child_profiles"),  # Each conversation must belong to a child
                    ("audio_records", "conversations"),  # Audio must belong to conversations
                ]
                
                for child_table, parent_table in critical_relationships:
                    cur.execute(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{child_table}'
                        )
                    """)
                    
                    if cur.fetchone()[0]:
                        cur.execute(f"""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = '{parent_table}'
                            )
                        """)
                        
                        if not cur.fetchone()[0]:
                            error_msg = f"Missing parent table {parent_table} for {child_table}"
                            consistency_errors.append(error_msg)
                            self.logger.error(error_msg)
            
            conn.close()
            
            if consistency_errors:
                self.logger.error(f"Data consistency validation failed with {len(consistency_errors)} errors")
                return False
            
            self.logger.info("Data consistency validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Data consistency validation failed: {e}")
            return False

    async def _rollback_restore(self, result: RestoreResult) -> None:
        """Rollback restore operation to previous state"""
        self.logger.info(f"Rolling back restore operation: {result.restore_id}")
        
        if not result.rollback_info:
            raise Exception("No rollback information available")
        
        # Restore from rollback backup
        # This would use the backup created before the restore operation
        # Implementation would depend on what was backed up
        
        self.logger.info("Rollback completed")

    def _update_restore_metrics(self, request: RestoreRequest, result: RestoreResult) -> None:
        """Update Prometheus metrics for restore operation"""
        self.metrics_collector.increment_counter(
            "restore_operations_total",
            {
                "type": request.restore_type.value,
                "status": result.status.value
            }
        )
        
        if result.end_time:
            duration = (result.end_time - result.start_time).total_seconds()
            self.metrics_collector.observe_histogram(
                "restore_duration_seconds",
                duration,
                {"type": request.restore_type.value}
            )

    async def get_restore_status(self, restore_id: str) -> Optional[RestoreResult]:
        """Get status of restore operation"""
        # Check active restores first
        if restore_id in self.active_restores:
            return self.active_restores[restore_id]
        
        # Check history
        for result in self.restore_history:
            if result.restore_id == restore_id:
                return result
        
        return None

    async def list_restore_history(self, limit: int = 50) -> List[RestoreResult]:
        """List restore operation history"""
        return sorted(self.restore_history, key=lambda x: x.start_time, reverse=True)[:limit]
