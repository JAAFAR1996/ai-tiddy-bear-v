"""
Configuration Backup Service for AI Teddy Bear Application

Handles backup of:
- Application configuration files
- Environment variables and secrets
- SSL certificates and keys
- Docker configurations
- Kubernetes manifests
- CI/CD configurations
"""

import asyncio
import logging
import json
import yaml
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union
from dataclasses import dataclass, asdict
import aiofiles
import aiofiles.os
from cryptography.fernet import Fernet

from ..security.crypto_utils import SecureVault
from ..monitoring.prometheus_metrics import PrometheusMetricsCollector


@dataclass
class ConfigItem:
    """Configuration item metadata"""
    name: str
    path: str
    config_type: str  # yaml, json, env, cert, key, docker, k8s
    sensitive: bool
    size_bytes: int
    checksum: str
    last_modified: datetime
    encrypted: bool = False


@dataclass
class ConfigBackupManifest:
    """Manifest for configuration backup"""
    backup_id: str
    timestamp: datetime
    config_items: List[ConfigItem]
    total_size_bytes: int
    encrypted: bool
    secrets_included: bool
    environment: str  # production, staging, development


@dataclass
class ConfigBackupResult:
    """Result of configuration backup"""
    success: bool
    backup_id: str
    backup_path: str
    config_count: int
    secrets_count: int
    size_bytes: int
    manifest: ConfigBackupManifest
    error_message: Optional[str] = None


class ConfigBackupService:
    """
    Configuration backup service that safely handles sensitive
    configuration data, secrets, and certificates.
    """

    def __init__(self,
                 backup_base_path: str,
                 encryption_key: str,
                 vault: Optional[SecureVault] = None,
                 metrics_collector: Optional[PrometheusMetricsCollector] = None):
        self.backup_base_path = Path(backup_base_path)
        self.encryption_key = encryption_key
        self.vault = vault
        self.metrics_collector = metrics_collector or PrometheusMetricsCollector()
        
        self.logger = logging.getLogger(__name__)
        self.backup_base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        self.fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        
        # Configuration file patterns and types
        self.config_patterns = {
            'yaml': ['*.yaml', '*.yml'],
            'json': ['*.json'],
            'env': ['.env*', '*.env'],
            'cert': ['*.pem', '*.crt', '*.cert'],
            'key': ['*.key', '*.private'],
            'docker': ['Dockerfile*', 'docker-compose*.yml', '.dockerignore'],
            'k8s': ['*.yaml', '*.yml'],  # In kubernetes/ directory
            'nginx': ['nginx.conf', '*.conf'],
            'script': ['*.sh', '*.py', '*.js'],
            'config': ['*.ini', '*.conf', '*.cfg', 'alembic.ini', 'pytest.ini']
        }
        
        # Sensitive file patterns
        self.sensitive_patterns = [
            '.env', 'secret', 'key', 'password', 'token', 'private',
            'cert', 'ssl', 'tls', 'credential', 'auth'
        ]
        
        # Default configuration paths to backup
        self.default_config_paths = [
            'config/',
            'deployment/',
            'kubernetes/',
            'nginx/',
            'scripts/',
            'docker-compose*.yml',
            'Dockerfile*',
            'alembic.ini',
            'pytest.ini',
            '.env*',
            '*.yaml',
            '*.yml',
            '*.json'
        ]

    async def create_backup(self,
                          config_paths: Optional[List[str]] = None,
                          include_secrets: bool = True,
                          environment: str = "production") -> ConfigBackupResult:
        """Create configuration backup"""
        backup_id = self._generate_backup_id()
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"Starting configuration backup: {backup_id}")
            
            # Use default paths if none specified
            if config_paths is None:
                config_paths = self.default_config_paths
            
            # Create backup directory
            backup_dir = self.backup_base_path / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Discover configuration files
            config_items = await self._discover_config_files(config_paths)
            
            if not config_items:
                self.logger.warning("No configuration files found to backup")
                return ConfigBackupResult(
                    success=True,
                    backup_id=backup_id,
                    backup_path=str(backup_dir),
                    config_count=0,
                    secrets_count=0,
                    size_bytes=0,
                    manifest=None
                )
            
            # Process configuration files
            processed_items = []
            secrets_count = 0
            total_size = 0
            
            for config_item in config_items:
                try:
                    # Skip secrets if not requested
                    if not include_secrets and config_item.sensitive:
                        self.logger.info(f"Skipping sensitive config: {config_item.name}")
                        continue
                    
                    # Process configuration item
                    processed_item = await self._process_config_item(config_item, backup_dir)
                    
                    if processed_item:
                        processed_items.append(processed_item)
                        total_size += processed_item.size_bytes
                        
                        if processed_item.sensitive:
                            secrets_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to process config {config_item.name}: {e}")
                    continue
            
            # Backup environment variables
            if include_secrets:
                env_backup = await self._backup_environment_variables(backup_dir)
                if env_backup:
                    processed_items.append(env_backup)
                    total_size += env_backup.size_bytes
                    secrets_count += 1
            
            # Backup vault secrets if available
            if include_secrets and self.vault:
                vault_backup = await self._backup_vault_secrets(backup_dir)
                if vault_backup:
                    processed_items.append(vault_backup)
                    total_size += vault_backup.size_bytes
                    secrets_count += 1
            
            # Create backup manifest
            manifest = ConfigBackupManifest(
                backup_id=backup_id,
                timestamp=start_time,
                config_items=processed_items,
                total_size_bytes=total_size,
                encrypted=True,  # All sensitive data is encrypted
                secrets_included=include_secrets,
                environment=environment
            )
            
            # Save manifest
            manifest_path = backup_dir / "manifest.json"
            await self._save_manifest(manifest, manifest_path)
            
            # Create backup archive
            archive_path = await self._create_backup_archive(backup_dir)
            
            # Update metrics
            self._update_backup_metrics(len(processed_items), secrets_count, total_size,
                                      (datetime.utcnow() - start_time).total_seconds())
            
            self.logger.info(f"Configuration backup completed: {backup_id} "
                           f"({len(processed_items)} files, {secrets_count} secrets)")
            
            return ConfigBackupResult(
                success=True,
                backup_id=backup_id,
                backup_path=str(archive_path),
                config_count=len(processed_items),
                secrets_count=secrets_count,
                size_bytes=total_size,
                manifest=manifest
            )
            
        except Exception as e:
            self.logger.error(f"Configuration backup failed: {backup_id}: {e}")
            return ConfigBackupResult(
                success=False,
                backup_id=backup_id,
                backup_path="",
                config_count=0,
                secrets_count=0,
                size_bytes=0,
                manifest=None,
                error_message=str(e)
            )

    def _generate_backup_id(self) -> str:
        """Generate unique backup ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"config_backup_{timestamp}"

    async def _discover_config_files(self, config_paths: List[str]) -> List[ConfigItem]:
        """Discover configuration files to backup"""
        config_items = []
        processed_paths = set()
        
        for path_pattern in config_paths:
            # Handle glob patterns
            if '*' in path_pattern:
                from glob import glob
                matching_paths = glob(path_pattern)
            else:
                matching_paths = [path_pattern]
            
            for path_str in matching_paths:
                path = Path(path_str)
                
                if path.is_file():
                    if str(path) not in processed_paths:
                        config_item = await self._create_config_item(path)
                        if config_item:
                            config_items.append(config_item)
                            processed_paths.add(str(path))
                
                elif path.is_dir():
                    # Recursively process directory
                    async for file_path in self._walk_config_directory(path):
                        if str(file_path) not in processed_paths:
                            config_item = await self._create_config_item(file_path)
                            if config_item:
                                config_items.append(config_item)
                                processed_paths.add(str(file_path))
        
        return config_items

    async def _walk_config_directory(self, directory: Path):
        """Walk directory and yield configuration files"""
        for item in directory.rglob('*'):
            if item.is_file() and self._is_config_file(item):
                yield item

    def _is_config_file(self, file_path: Path) -> bool:
        """Check if file is a configuration file"""
        filename = file_path.name.lower()
        
        # Check against config patterns
        for config_type, patterns in self.config_patterns.items():
            for pattern in patterns:
                if pattern.startswith('*'):
                    if filename.endswith(pattern[1:]):
                        return True
                elif pattern.endswith('*'):
                    if filename.startswith(pattern[:-1]):
                        return True
                else:
                    if filename == pattern.lower():
                        return True
        
        return False

    async def _create_config_item(self, file_path: Path) -> Optional[ConfigItem]:
        """Create configuration item from file"""
        try:
            if not file_path.exists():
                return None
            
            stat = file_path.stat()
            config_type = self._determine_config_type(file_path)
            sensitive = self._is_sensitive_file(file_path)
            
            # Calculate checksum
            checksum = await self._calculate_checksum(file_path)
            
            return ConfigItem(
                name=file_path.name,
                path=str(file_path),
                config_type=config_type,
                sensitive=sensitive,
                size_bytes=stat.st_size,
                checksum=checksum,
                last_modified=datetime.fromtimestamp(stat.st_mtime)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create config item for {file_path}: {e}")
            return None

    def _determine_config_type(self, file_path: Path) -> str:
        """Determine configuration file type"""
        filename = file_path.name.lower()
        suffix = file_path.suffix.lower()
        
        # Check by directory
        if 'kubernetes' in str(file_path).lower():
            return 'k8s'
        elif 'nginx' in str(file_path).lower():
            return 'nginx'
        elif 'docker' in filename:
            return 'docker'
        
        # Check by extension
        if suffix in ['.yaml', '.yml']:
            return 'yaml'
        elif suffix == '.json':
            return 'json'
        elif suffix in ['.pem', '.crt', '.cert']:
            return 'cert'
        elif suffix == '.key' or 'private' in filename:
            return 'key'
        elif '.env' in filename or filename.startswith('env'):
            return 'env'
        elif suffix in ['.sh', '.py', '.js']:
            return 'script'
        elif suffix in ['.ini', '.conf', '.cfg']:
            return 'config'
        
        return 'other'

    def _is_sensitive_file(self, file_path: Path) -> bool:
        """Check if file contains sensitive data"""
        filename = file_path.name.lower()
        path_str = str(file_path).lower()
        
        for pattern in self.sensitive_patterns:
            if pattern in filename or pattern in path_str:
                return True
        
        return False

    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum"""
        import hashlib
        
        hash_sha256 = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()

    async def _process_config_item(self, config_item: ConfigItem, backup_dir: Path) -> Optional[ConfigItem]:
        """Process configuration item for backup"""
        try:
            source_path = Path(config_item.path)
            
            # Skip if file no longer exists
            if not source_path.exists():
                return None
            
            # Create backup filename with path structure
            relative_path = source_path.relative_to(Path.cwd()) if source_path.is_absolute() else source_path
            backup_file_path = backup_dir / relative_path
            backup_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            if config_item.sensitive:
                # Encrypt sensitive files
                await self._copy_and_encrypt_file(source_path, backup_file_path)
                config_item.encrypted = True
            else:
                # Copy non-sensitive files as-is
                async with aiofiles.open(source_path, 'rb') as src:
                    async with aiofiles.open(backup_file_path, 'wb') as dst:
                        content = await src.read()
                        await dst.write(content)
            
            # Update size after processing
            if backup_file_path.exists():
                config_item.size_bytes = backup_file_path.stat().st_size
            
            return config_item
            
        except Exception as e:
            self.logger.error(f"Failed to process config item {config_item.name}: {e}")
            return None

    async def _copy_and_encrypt_file(self, source_path: Path, dest_path: Path) -> None:
        """Copy and encrypt a sensitive file"""
        # Read source file
        async with aiofiles.open(source_path, 'rb') as f:
            content = await f.read()
        
        # Encrypt content
        encrypted_content = self.fernet.encrypt(content)
        
        # Write encrypted content with .enc extension
        encrypted_path = dest_path.with_suffix(dest_path.suffix + '.enc')
        async with aiofiles.open(encrypted_path, 'wb') as f:
            await f.write(encrypted_content)

    async def _backup_environment_variables(self, backup_dir: Path) -> Optional[ConfigItem]:
        """Backup environment variables"""
        try:
            # Get current environment variables
            env_vars = dict(os.environ)
            
            # Filter sensitive environment variables
            sensitive_vars = {}
            for key, value in env_vars.items():
                if any(pattern.upper() in key.upper() for pattern in self.sensitive_patterns):
                    sensitive_vars[key] = value
            
            if not sensitive_vars:
                return None
            
            # Create environment backup file
            env_backup_path = backup_dir / "environment_variables.json.enc"
            
            # Encrypt and save
            env_data = json.dumps(sensitive_vars, indent=2)
            encrypted_data = self.fernet.encrypt(env_data.encode())
            
            async with aiofiles.open(env_backup_path, 'wb') as f:
                await f.write(encrypted_data)
            
            # Calculate checksum
            checksum = await self._calculate_checksum(env_backup_path)
            
            return ConfigItem(
                name="environment_variables.json",
                path=str(env_backup_path),
                config_type="env",
                sensitive=True,
                size_bytes=env_backup_path.stat().st_size,
                checksum=checksum,
                last_modified=datetime.utcnow(),
                encrypted=True
            )
            
        except Exception as e:
            self.logger.error(f"Failed to backup environment variables: {e}")
            return None

    async def _backup_vault_secrets(self, backup_dir: Path) -> Optional[ConfigItem]:
        """Backup secrets from vault"""
        if not self.vault:
            return None
        
        try:
            # Get all secrets from vault
            secrets = await self.vault.get_all_secrets()
            
            if not secrets:
                return None
            
            # Create vault backup file
            vault_backup_path = backup_dir / "vault_secrets.json.enc"
            
            # Double encrypt vault secrets (they're already encrypted in vault)
            vault_data = json.dumps(secrets, indent=2)
            encrypted_data = self.fernet.encrypt(vault_data.encode())
            
            async with aiofiles.open(vault_backup_path, 'wb') as f:
                await f.write(encrypted_data)
            
            # Calculate checksum
            checksum = await self._calculate_checksum(vault_backup_path)
            
            return ConfigItem(
                name="vault_secrets.json",
                path=str(vault_backup_path),
                config_type="vault",
                sensitive=True,
                size_bytes=vault_backup_path.stat().st_size,
                checksum=checksum,
                last_modified=datetime.utcnow(),
                encrypted=True
            )
            
        except Exception as e:
            self.logger.error(f"Failed to backup vault secrets: {e}")
            return None

    async def _save_manifest(self, manifest: ConfigBackupManifest, manifest_path: Path) -> None:
        """Save backup manifest"""
        manifest_dict = asdict(manifest)
        
        # Convert datetime objects
        manifest_dict['timestamp'] = manifest.timestamp.isoformat()
        for item in manifest_dict['config_items']:
            item['last_modified'] = item['last_modified'].isoformat()
        
        async with aiofiles.open(manifest_path, 'w') as f:
            await f.write(json.dumps(manifest_dict, indent=2))

    async def _create_backup_archive(self, backup_dir: Path) -> Path:
        """Create compressed archive of backup"""
        archive_path = backup_dir.with_suffix('.tar.gz')
        
        # Create tar.gz archive
        import tarfile
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(backup_dir, arcname=backup_dir.name)
        
        # Remove original directory
        shutil.rmtree(backup_dir)
        
        return archive_path

    def _update_backup_metrics(self, config_count: int, secrets_count: int,
                             size_bytes: int, duration_seconds: float) -> None:
        """Update Prometheus metrics"""
        self.metrics_collector.increment_counter("config_backups_total")
        
        self.metrics_collector.observe_histogram(
            "config_backup_file_count",
            config_count
        )
        
        self.metrics_collector.observe_histogram(
            "config_backup_secrets_count",
            secrets_count
        )
        
        self.metrics_collector.observe_histogram(
            "config_backup_size_bytes",
            size_bytes
        )
        
        self.metrics_collector.observe_histogram(
            "config_backup_duration_seconds",
            duration_seconds
        )

    async def list_backups(self, limit: int = 50) -> List[ConfigBackupManifest]:
        """List available configuration backups"""
        backups = []
        
        for backup_file in self.backup_base_path.glob("config_backup_*.tar.gz"):
            try:
                # Extract and read manifest
                manifest = await self._load_manifest_from_archive(backup_file)
                backups.append(manifest)
                
            except Exception as e:
                self.logger.error(f"Failed to load manifest from {backup_file}: {e}")
                continue
        
        # Sort by timestamp, newest first
        backups.sort(key=lambda x: x.timestamp, reverse=True)
        
        return backups[:limit]

    async def _load_manifest_from_archive(self, archive_path: Path) -> ConfigBackupManifest:
        """Load manifest from backup archive"""
        import tarfile
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract archive
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(temp_dir)
            
            # Find manifest file
            manifest_files = list(Path(temp_dir).rglob("manifest.json"))
            if not manifest_files:
                raise Exception("Manifest not found in backup archive")
            
            # Load manifest
            async with aiofiles.open(manifest_files[0], 'r') as f:
                content = await f.read()
                data = json.loads(content)
            
            # Parse manifest
            manifest = ConfigBackupManifest(
                backup_id=data['backup_id'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                config_items=[],  # Would parse config items here
                total_size_bytes=data['total_size_bytes'],
                encrypted=data['encrypted'],
                secrets_included=data['secrets_included'],
                environment=data['environment']
            )
            
            return manifest

    async def restore_config(self, backup_id: str, target_path: Optional[str] = None) -> bool:
        """Restore configuration from backup"""
        try:
            # Find backup archive
            backup_file = self.backup_base_path / f"{backup_id}.tar.gz"
            
            if not backup_file.exists():
                self.logger.error(f"Backup not found: {backup_id}")
                return False
            
            # Set target path
            if target_path is None:
                target_path = Path.cwd()
            else:
                target_path = Path(target_path)
            
            # Extract archive
            import tarfile
            
            with tarfile.open(backup_file, 'r:gz') as tar:
                tar.extractall(target_path)
            
            self.logger.info(f"Configuration restored from backup: {backup_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore configuration backup {backup_id}: {e}")
            return False