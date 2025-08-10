"""
File handling utilities for secure file operations.
Provides file validation, processing, and storage utilities.

Security Notes:
- All audio and metadata files are stored with strict permissions (0600).
- Files are stored with integrity verification (SHA-256 hash).
- COPPA compliance enforced: All child audio is flagged as protected and auditable.
- Audit logs are saved monthly with timestamps and operation metadata.
- Temporary files are cleaned after 24h by default via cleanup_temp_files().
"""

import os
import hashlib
import mimetypes
from pathlib import Path
from typing import Dict, Any, List
import tempfile
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class FileHandler:
    """General file handling utilities."""

    def __init__(
        self, max_file_size: int = 10 * 1024 * 1024, allowed_types: List[str] = None
    ):
        self.max_file_size = max_file_size  # 10MB default
        self.allowed_types = allowed_types or [
            "audio/wav",
            "audio/mp3",
            "audio/ogg",
            "image/png",
            "image/jpeg",
        ]

    def validate_file(self, file_path: str) -> Dict[str, Any]:
        # Validate file for safety and compliance
        if not os.path.exists(file_path):
            return {"valid": False, "reason": "File does not exist"}

        file_stat = os.stat(file_path)
        file_size = file_stat.st_size

        # Check file size
        if file_size > self.max_file_size:
            return {"valid": False, "reason": f"File too large: {file_size} bytes"}

        # Check file type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type not in self.allowed_types:
            return {"valid": False, "reason": f"File type not allowed: {mime_type}"}

        # Check for malicious content
        if self._contains_malicious_content(file_path):
            return {"valid": False, "reason": "File contains malicious content"}

        return {
            "valid": True,
            "file_size": file_size,
            "mime_type": mime_type,
            "file_hash": self.calculate_file_hash(file_path),
        }

    def calculate_file_hash(self, file_path: str, algorithm: str = "sha256") -> str:
        # Calculate file hash for integrity verification
        hash_obj = hashlib.new(algorithm)

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def secure_filename(self, filename: str) -> str:
        # Generate secure filename by removing dangerous characters
        # Remove path separators and dangerous characters
        filename = os.path.basename(filename)
        filename = "".join(c for c in filename if c.isalnum() or c in "._-")

        # Ensure it's not empty and has reasonable length
        if not filename or len(filename) > 255:
            filename = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return filename

    def create_temp_file(self, suffix: str = None, prefix: str = "temp_") -> str:
        # Create temporary file with secure permissions
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix, prefix=prefix
        ) as temp_file:
            # Set secure file permissions (owner read/write only)
            os.chmod(temp_file.name, 0o600)
            return temp_file.name

    def safe_file_copy(self, source: str, destination: str) -> bool:
        # Safely copy file with validation
        try:
            # Validate source file
            validation = self.validate_file(source)
            if not validation["valid"]:
                return False

            # Ensure destination directory exists
            dest_dir = os.path.dirname(destination)
            os.makedirs(dest_dir, exist_ok=True)

            # Copy file in chunks
            with open(source, "rb") as src, open(destination, "wb") as dst:
                while True:
                    chunk = src.read(64 * 1024)  # 64KB chunks
                    if not chunk:
                        break
                    dst.write(chunk)

            # Set secure permissions
            os.chmod(destination, 0o600)

            return True

        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"File copy error: {e}", exc_info=True)
            return False

    def cleanup_temp_files(self, temp_dir: str = None, max_age_hours: int = 24) -> int:
        # Clean up old temporary files
        if temp_dir is None:
            temp_dir = tempfile.gettempdir()

        cleaned_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        try:
            for file_path in Path(temp_dir).glob("temp_*"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    cleaned_count += 1
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Cleanup error: {e}", exc_info=True)

        return cleaned_count

    def _contains_malicious_content(self, file_path: str) -> bool:
        # Check file for malicious content (simplified)
        # This is a basic implementation
        # In production, use comprehensive malware scanning

        dangerous_signatures = [
            b"\x4d\x5a",  # Windows PE header
            b"#!/bin/sh",  # Shell script
            b"#!/bin/bash",  # Bash script
            b"<script",  # HTML script tag
        ]

        try:
            with open(file_path, "rb") as f:
                header = f.read(1024)  # Read first 1KB

                for signature in dangerous_signatures:
                    if signature in header:
                        return True

        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.warning(
                f"Failed to read file {file_path} for malware check: {e}", exc_info=True
            )
            return False  # Don't assume malicious by default

        return False


class SecureFileOperations:
    """Secure file operations for sensitive data."""

    def __init__(self, encryption_key: bytes = None):
        self.file_handler = FileHandler()
        self.encryption_key = encryption_key

    def store_child_audio(
        self, audio_data: bytes, child_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Securely store child audio data
        # Generate secure filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"child_audio_{child_id}_{timestamp}.wav"
        secure_filename = self.file_handler.secure_filename(filename)

        # Create secure storage directory
        storage_dir = os.path.join(
            "secure_storage", "audio", child_id[:2]
        )  # Shard by first 2 chars
        os.makedirs(storage_dir, exist_ok=True)

        file_path = os.path.join(storage_dir, secure_filename)

        try:
            # Store audio data
            with open(file_path, "wb") as f:
                f.write(audio_data)

            # Set secure permissions
            os.chmod(file_path, 0o600)

            # Calculate file hash for integrity
            file_hash = self.file_handler.calculate_file_hash(file_path)

            # Store metadata
            metadata_path = file_path + ".meta"
            metadata_with_hash = {
                **metadata,
                "file_hash": file_hash,
                "stored_at": datetime.now().isoformat(),
                "child_id": child_id,
                "coppa_protected": True,
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_with_hash, f)

            os.chmod(metadata_path, 0o600)

            return {
                "success": True,
                "file_path": file_path,
                "file_hash": file_hash,
                "metadata_path": metadata_path,
            }

        except (OSError, PermissionError, FileNotFoundError) as e:
            return {"success": False, "error": str(e)}

    def retrieve_child_audio(
        self, child_id: str, file_identifier: str
    ) -> Dict[str, Any]:
        # Securely retrieve child audio data
        # Construct file path
        storage_dir = os.path.join("secure_storage", "audio", child_id[:2])
        file_path = os.path.join(storage_dir, file_identifier)
        metadata_path = file_path + ".meta"

        if not os.path.exists(file_path) or not os.path.exists(metadata_path):
            return {"success": False, "error": "File not found"}

        try:
            # Load and verify metadata
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            # Verify file integrity
            current_hash = self.file_handler.calculate_file_hash(file_path)
            if current_hash != metadata.get("file_hash"):
                return {"success": False, "error": "File integrity check failed"}

            # Verify child ownership
            if metadata.get("child_id") != child_id:
                return {"success": False, "error": "Access denied"}

            # Read audio data
            with open(file_path, "rb") as f:
                audio_data = f.read()

            return {"success": True, "audio_data": audio_data, "metadata": metadata}

        except (OSError, PermissionError, FileNotFoundError, ValueError) as e:
            return {"success": False, "error": str(e)}

    def delete_child_data(
        self, child_id: str, file_identifier: str = None
    ) -> Dict[str, Any]:
        # Securely delete child data files
        storage_dir = os.path.join("secure_storage", "audio", child_id[:2])

        deleted_files = []

        try:
            if file_identifier:
                # Delete specific file
                file_path = os.path.join(storage_dir, file_identifier)
                metadata_path = file_path + ".meta"

                for path in [file_path, metadata_path]:
                    if os.path.exists(path):
                        self._secure_delete(path)
                        deleted_files.append(path)
            else:
                # Delete all files for child
                if os.path.exists(storage_dir):
                    for file_path in Path(storage_dir).glob(
                        f"child_audio_{child_id}_*"
                    ):
                        self._secure_delete(str(file_path))
                        deleted_files.append(str(file_path))

                        # Delete corresponding metadata
                        meta_path = str(file_path) + ".meta"
                        if os.path.exists(meta_path):
                            self._secure_delete(meta_path)
                            deleted_files.append(meta_path)

            return {
                "success": True,
                "deleted_files": deleted_files,
                "deletion_timestamp": datetime.now().isoformat(),
            }

        except (OSError, PermissionError, FileNotFoundError) as e:
            return {"success": False, "error": str(e), "deleted_files": deleted_files}

    def audit_file_access(
        self, child_id: str, operation: str, details: Dict[str, Any]
    ) -> None:
        # Audit file access operations
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "child_id": child_id,
            "operation": operation,
            "details": details,
            "coppa_audit": True,
        }

        # In production, this would go to a secure audit log
        audit_file = os.path.join(
            "audit_logs", f"file_access_{datetime.now().strftime('%Y%m')}.log"
        )
        os.makedirs(os.path.dirname(audit_file), exist_ok=True)

        # Check audit file size (max 10MB)
        if (
            os.path.exists(audit_file)
            and os.path.getsize(audit_file) > 10 * 1024 * 1024
        ):
            logger.warning(f"Audit log too large: {audit_file}")
            # Optionally: rotate, archive, or refuse writing
            return

        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry) + "\n")

    def _secure_delete(self, file_path: str) -> None:
        # Securely delete file by overwriting before deletion
        if not os.path.exists(file_path):
            return

        # Get file size
        file_size = os.path.getsize(file_path)

        # Overwrite with random data
        if file_size == 0:
            logger.warning(f"Attempted to secure delete an empty file: {file_path}")
        else:
            with open(file_path, "r+b") as f:
                for _ in range(3):  # Multiple passes
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())

        # Finally delete the file
        os.unlink(file_path)

    def get_storage_stats(self) -> Dict[str, Any]:
        # Get storage statistics for monitoring
        storage_root = "secure_storage"

        if not os.path.exists(storage_root):
            return {"total_files": 0, "total_size": 0}

        total_files = 0
        total_size = 0

        for root, dirs, files in os.walk(storage_root):
            for file in files:
                if not file.endswith(".meta"):  # Don't count metadata files
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    total_files += 1

        return {
            "total_files": total_files,
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "last_updated": datetime.now().isoformat(),
        }


# Global utility functions
def ensure_directory_exists(directory_path: str) -> bool:
    """Ensure directory exists, create if it doesn't."""
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory_path}: {e}")
        return False


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except Exception:
        return 0


def safe_remove_file(file_path: str) -> bool:
    """Safely remove a file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        logger.error(f"Failed to remove file {file_path}: {e}")
        return False
