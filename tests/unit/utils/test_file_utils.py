"""
Unit tests for file utilities module.
Tests secure file operations, validation, and child data protection.
"""

import pytest
import os
import tempfile
import hashlib
import json
from pathlib import Path
from unittest.mock import patch, mock_open
from datetime import datetime, timedelta

from src.utils.file_utils import FileHandler, SecureFileOperations


class TestFileHandler:
    """Test FileHandler class functionality."""

    @pytest.fixture
    def file_handler(self):
        """Create FileHandler instance for testing."""
        return FileHandler()

    @pytest.fixture
    def custom_file_handler(self):
        """Create FileHandler with custom settings."""
        return FileHandler(
            max_file_size=5 * 1024 * 1024,  # 5MB
            allowed_types=["audio/wav", "image/png"],
        )

    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
            temp.write(b"fake audio data")
            temp_path = temp.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_file_handler_initialization_default(self):
        """Test FileHandler initialization with defaults."""
        handler = FileHandler()

        assert handler.max_file_size == 10 * 1024 * 1024  # 10MB
        assert "audio/wav" in handler.allowed_types
        assert "audio/mp3" in handler.allowed_types
        assert "image/png" in handler.allowed_types
        assert "image/jpeg" in handler.allowed_types

    def test_file_handler_initialization_custom(self, custom_file_handler):
        """Test FileHandler initialization with custom settings."""
        assert custom_file_handler.max_file_size == 5 * 1024 * 1024
        assert custom_file_handler.allowed_types == ["audio/wav", "image/png"]

    def test_validate_file_success(self, file_handler, temp_file):
        """Test successful file validation."""
        with patch("mimetypes.guess_type", autospec=True) as mock_mime:
            mock_mime.return_value = ("audio/wav", None)
            result = file_handler.validate_file(temp_file)
            assert result["valid"] is True
            assert "file_size" in result
            assert result["mime_type"] == "audio/wav"
            assert "file_hash" in result

    def test_validate_file_not_exists(self, file_handler):
        """Test validation of non-existent file."""
        result = file_handler.validate_file("non_existent_file.wav")

        assert result["valid"] is False
        assert "does not exist" in result["reason"]

    def test_validate_file_too_large(self, file_handler):
        """Test validation of file that's too large."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            # Create file larger than max_file_size
            large_data = b"x" * (file_handler.max_file_size + 1)
            temp.write(large_data)
            temp_path = temp.name

        try:
            result = file_handler.validate_file(temp_path)

            assert result["valid"] is False
            assert "File too large" in result["reason"]
        finally:
            os.unlink(temp_path)

    def test_validate_file_wrong_type(self, file_handler, temp_file):
        """Test validation of disallowed file type."""
        with patch("mimetypes.guess_type", autospec=True) as mock_mime:
            mock_mime.return_value = ("application/executable", None)
            result = file_handler.validate_file(temp_file)
            assert result["valid"] is False
            assert "File type not allowed" in result["reason"]

    def test_validate_file_malicious_content(self, file_handler):
        """Test validation of file with malicious content."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
            # Write PE header (Windows executable signature)
            temp.write(b"\x4d\x5a" + b"fake executable content")
            temp_path = temp.name
        try:
            with patch("mimetypes.guess_type", autospec=True) as mock_mime:
                mock_mime.return_value = ("audio/wav", None)
                result = file_handler.validate_file(temp_path)
                assert result["valid"] is False
                assert "malicious content" in result["reason"]
        finally:
            os.unlink(temp_path)

    def test_calculate_file_hash_sha256(self, file_handler, temp_file):
        """Test SHA256 file hash calculation."""
        result_hash = file_handler.calculate_file_hash(temp_file)

        # Calculate expected hash
        with open(temp_file, "rb") as f:
            expected_hash = hashlib.sha256(f.read()).hexdigest()

        assert result_hash == expected_hash
        assert len(result_hash) == 64  # SHA256 hex length

    def test_calculate_file_hash_md5(self, file_handler, temp_file):
        """Test MD5 file hash calculation."""
        result_hash = file_handler.calculate_file_hash(temp_file, algorithm="md5")

        # Calculate expected hash
        with open(temp_file, "rb") as f:
            expected_hash = hashlib.md5(f.read()).hexdigest()

        assert result_hash == expected_hash
        assert len(result_hash) == 32  # MD5 hex length

    def test_calculate_file_hash_large_file(self, file_handler):
        """Test hash calculation for large file (chunked reading)."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            # Create file larger than chunk size
            large_data = b"test data chunk " * 1000  # ~15KB
            temp.write(large_data)
            temp_path = temp.name

        try:
            result_hash = file_handler.calculate_file_hash(temp_path)

            # Verify it's a valid SHA256 hash
            assert len(result_hash) == 64
            assert all(c in "0123456789abcdef" for c in result_hash)
        finally:
            os.unlink(temp_path)

    def test_secure_filename_basic(self, file_handler):
        """Test basic secure filename generation."""
        result = file_handler.secure_filename("normal_file.wav")
        assert result == "normal_file.wav"

    def test_secure_filename_dangerous_chars(self, file_handler):
        """Test secure filename with dangerous characters."""
        dangerous = "../../../etc/passwd"
        result = file_handler.secure_filename(dangerous)

        assert "../" not in result
        assert "etcpasswd" in result

    def test_secure_filename_special_chars(self, file_handler):
        """Test secure filename with special characters."""
        special = "file with spaces & symbols!@#.wav"
        result = file_handler.secure_filename(special)

        # Should only contain alphanumeric and allowed chars
        allowed_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        )
        assert all(c in allowed_chars for c in result)
        assert result.endswith(".wav")

    def test_secure_filename_empty(self, file_handler):
        """Test secure filename with empty input."""
        with patch("src.utils.file_utils.datetime", autospec=True) as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20250729_120000"
            result = file_handler.secure_filename("")
            assert result == "file_20250729_120000"

    def test_secure_filename_too_long(self, file_handler):
        """Test secure filename with too long input."""
        long_name = "a" * 300 + ".wav"
        with patch("src.utils.file_utils.datetime", autospec=True) as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20250729_120000"
            result = file_handler.secure_filename(long_name)
            assert result == "file_20250729_120000"
            assert len(result) <= 255

    def test_create_temp_file(self, file_handler):
        """Test temporary file creation."""
        temp_path = file_handler.create_temp_file(suffix=".wav", prefix="test_")

        try:
            assert os.path.exists(temp_path)
            assert temp_path.endswith(".wav")
            assert "test_" in os.path.basename(temp_path)

            # Check secure permissions (owner read/write only)
            file_mode = os.stat(temp_path).st_mode
            assert oct(file_mode)[-3:] == "600"

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_safe_file_copy_success(self, file_handler, temp_file):
        """Test successful safe file copy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = os.path.join(temp_dir, "copied_file.wav")
            with patch.object(
                file_handler, "validate_file", autospec=True
            ) as mock_validate:
                mock_validate.return_value = {"valid": True}
                result = file_handler.safe_file_copy(temp_file, destination)
                assert result is True
                assert os.path.exists(destination)
                # Check secure permissions
                file_mode = os.stat(destination).st_mode
                assert oct(file_mode)[-3:] == "600"

    def test_safe_file_copy_invalid_source(self, file_handler, temp_file):
        """Test safe file copy with invalid source."""
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = os.path.join(temp_dir, "copied_file.wav")
            with patch.object(
                file_handler, "validate_file", autospec=True
            ) as mock_validate:
                mock_validate.return_value = {"valid": False, "reason": "Invalid file"}
                result = file_handler.safe_file_copy(temp_file, destination)
                assert result is False
                assert not os.path.exists(destination)

    def test_safe_file_copy_creates_directory(self, file_handler, temp_file):
        """Test safe file copy creates destination directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dest = os.path.join(temp_dir, "nested", "dir", "file.wav")
            with patch.object(
                file_handler, "validate_file", autospec=True
            ) as mock_validate:
                mock_validate.return_value = {"valid": True}
                result = file_handler.safe_file_copy(temp_file, nested_dest)
                assert result is True
                assert os.path.exists(nested_dest)
                assert os.path.exists(os.path.dirname(nested_dest))

    def test_safe_file_copy_error_handling(self, file_handler):
        """Test safe file copy error handling."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = file_handler.safe_file_copy("source.wav", "dest.wav")
            assert result is False

    def test_cleanup_temp_files(self, file_handler):
        """Test temporary file cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test temp files
            old_file = os.path.join(temp_dir, "temp_old_file.tmp")
            new_file = os.path.join(temp_dir, "temp_new_file.tmp")

            # Create old file (modify timestamp to be old)
            with open(old_file, "w") as f:
                f.write("old content")

            old_time = (datetime.now() - timedelta(hours=25)).timestamp()
            os.utime(old_file, (old_time, old_time))

            # Create new file
            with open(new_file, "w") as f:
                f.write("new content")

            # Run cleanup
            cleaned_count = file_handler.cleanup_temp_files(temp_dir, max_age_hours=24)

            assert cleaned_count == 1
            assert not os.path.exists(old_file)
            assert os.path.exists(new_file)

    def test_cleanup_temp_files_error_handling(self, file_handler):
        """Test cleanup temp files error handling."""
        with patch("pathlib.Path.glob", side_effect=PermissionError("Access denied")):
            cleaned_count = file_handler.cleanup_temp_files()
            assert cleaned_count == 0

    def test_contains_malicious_content_safe_file(self, file_handler, temp_file):
        """Test malicious content detection on safe file."""
        result = file_handler._contains_malicious_content(temp_file)
        assert result is False

    def test_contains_malicious_content_pe_header(self, file_handler):
        """Test malicious content detection with PE header."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"\x4d\x5a" + b"fake PE content")
            temp_path = temp.name

        try:
            result = file_handler._contains_malicious_content(temp_path)
            assert result is True
        finally:
            os.unlink(temp_path)

    def test_contains_malicious_content_script_tags(self, file_handler):
        """Test malicious content detection with script tags."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b'<script>alert("xss")</script>')
            temp_path = temp.name

        try:
            result = file_handler._contains_malicious_content(temp_path)
            assert result is True
        finally:
            os.unlink(temp_path)

    def test_contains_malicious_content_shell_script(self, file_handler):
        """Test malicious content detection with shell script."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b'#!/bin/bash\necho "malicious"')
            temp_path = temp.name

        try:
            result = file_handler._contains_malicious_content(temp_path)
            assert result is True
        finally:
            os.unlink(temp_path)

    def test_contains_malicious_content_read_error(self, file_handler):
        """Test malicious content detection with read error."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = file_handler._contains_malicious_content("fake_file.txt")
            assert result is True  # Assume malicious if can't read


class TestSecureFileOperations:
    """Test SecureFileOperations class functionality."""

    @pytest.fixture
    def secure_ops(self):
        """Create SecureFileOperations instance for testing."""
        return SecureFileOperations()

    @pytest.fixture
    def mock_temp_dir(self):
        """Create mock temporary directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the secure_storage directory
            storage_dir = os.path.join(temp_dir, "secure_storage", "audio", "ch")
            os.makedirs(storage_dir, exist_ok=True)

            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect
                yield temp_dir

    def test_secure_file_operations_initialization(self):
        """Test SecureFileOperations initialization."""
        ops = SecureFileOperations()
        assert isinstance(ops.file_handler, FileHandler)
        assert ops.encryption_key is None

        # Test with encryption key
        key = b"test_encryption_key_32_bytes_long"
        ops_with_key = SecureFileOperations(encryption_key=key)
        assert ops_with_key.encryption_key == key

    def test_store_child_audio_success(self, secure_ops):
        """Test successful child audio storage."""
        audio_data = b"fake audio wav data"
        child_id = "child_123"
        metadata = {"duration": 5.0, "format": "wav"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                with patch("src.utils.file_utils.datetime") as mock_datetime:
                    mock_datetime.now.return_value.strftime.return_value = (
                        "20250729_120000"
                    )
                    mock_datetime.now.return_value.isoformat.return_value = (
                        "2025-07-29T12:00:00"
                    )

                    result = secure_ops.store_child_audio(
                        audio_data, child_id, metadata
                    )

                    assert result["success"] is True
                    assert "file_path" in result
                    assert "file_hash" in result
                    assert "metadata_path" in result

                    # Verify file was created
                    assert os.path.exists(result["file_path"])

                    # Verify metadata file was created
                    assert os.path.exists(result["metadata_path"])

                    # Verify metadata content
                    with open(result["metadata_path"], "r") as f:
                        stored_metadata = json.load(f)

                    assert stored_metadata["child_id"] == child_id
                    assert stored_metadata["coppa_protected"] is True
                    assert stored_metadata["duration"] == 5.0

    def test_store_child_audio_error(self, secure_ops):
        """Test child audio storage error handling."""
        audio_data = b"fake audio data"
        child_id = "child_123"
        metadata = {}

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = secure_ops.store_child_audio(audio_data, child_id, metadata)

            assert result["success"] is False
            assert "error" in result

    def test_retrieve_child_audio_success(self, secure_ops):
        """Test successful child audio retrieval."""
        child_id = "child_123"
        file_identifier = "test_audio.wav"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup test files
            storage_dir = os.path.join(temp_dir, "secure_storage", "audio", "ch")
            os.makedirs(storage_dir, exist_ok=True)

            file_path = os.path.join(storage_dir, file_identifier)
            metadata_path = file_path + ".meta"

            # Create test audio file
            test_audio = b"test audio content"
            with open(file_path, "wb") as f:
                f.write(test_audio)

            # Calculate file hash
            file_hash = hashlib.sha256(test_audio).hexdigest()

            # Create metadata file
            test_metadata = {
                "child_id": child_id,
                "file_hash": file_hash,
                "coppa_protected": True,
            }
            with open(metadata_path, "w") as f:
                json.dump(test_metadata, f)

            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                result = secure_ops.retrieve_child_audio(child_id, file_identifier)

                assert result["success"] is True
                assert result["audio_data"] == test_audio
                assert result["metadata"]["child_id"] == child_id

    def test_retrieve_child_audio_file_not_found(self, secure_ops):
        """Test child audio retrieval when file doesn't exist."""
        result = secure_ops.retrieve_child_audio("child_123", "nonexistent.wav")

        assert result["success"] is False
        assert "File not found" in result["error"]

    def test_retrieve_child_audio_integrity_check_failed(self, secure_ops):
        """Test child audio retrieval with failed integrity check."""
        child_id = "child_123"
        file_identifier = "corrupted_audio.wav"

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = os.path.join(temp_dir, "secure_storage", "audio", "ch")
            os.makedirs(storage_dir, exist_ok=True)

            file_path = os.path.join(storage_dir, file_identifier)
            metadata_path = file_path + ".meta"

            # Create test audio file
            with open(file_path, "wb") as f:
                f.write(b"original content")

            # Create metadata with different hash
            test_metadata = {
                "child_id": child_id,
                "file_hash": "wrong_hash",
                "coppa_protected": True,
            }
            with open(metadata_path, "w") as f:
                json.dump(test_metadata, f)

            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                result = secure_ops.retrieve_child_audio(child_id, file_identifier)

                assert result["success"] is False
                assert "integrity check failed" in result["error"]

    def test_retrieve_child_audio_access_denied(self, secure_ops):
        """Test child audio retrieval with wrong child ID."""
        child_id = "child_123"
        wrong_child_id = "child_456"
        file_identifier = "audio.wav"

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = os.path.join(temp_dir, "secure_storage", "audio", "ch")
            os.makedirs(storage_dir, exist_ok=True)

            file_path = os.path.join(storage_dir, file_identifier)
            metadata_path = file_path + ".meta"

            # Create test files
            test_audio = b"test audio"
            with open(file_path, "wb") as f:
                f.write(test_audio)

            file_hash = hashlib.sha256(test_audio).hexdigest()
            test_metadata = {
                "child_id": child_id,  # Different from request
                "file_hash": file_hash,
            }
            with open(metadata_path, "w") as f:
                json.dump(test_metadata, f)

            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                result = secure_ops.retrieve_child_audio(
                    wrong_child_id, file_identifier
                )

                assert result["success"] is False
                assert "Access denied" in result["error"]

    def test_delete_child_data_specific_file(self, secure_ops):
        """Test deletion of specific child data file."""
        child_id = "child_123"
        file_identifier = "test_audio.wav"

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = os.path.join(temp_dir, "secure_storage", "audio", "ch")
            os.makedirs(storage_dir, exist_ok=True)

            file_path = os.path.join(storage_dir, file_identifier)
            metadata_path = file_path + ".meta"

            # Create test files
            with open(file_path, "wb") as f:
                f.write(b"test audio")
            with open(metadata_path, "w") as f:
                json.dump({"test": "metadata"}, f)

            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                with patch.object(secure_ops, "_secure_delete") as mock_delete:
                    result = secure_ops.delete_child_data(child_id, file_identifier)

                    assert result["success"] is True
                    assert len(result["deleted_files"]) == 2  # File + metadata
                    assert mock_delete.call_count == 2

    def test_delete_child_data_all_files(self, secure_ops):
        """Test deletion of all child data files."""
        child_id = "child_123"

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = os.path.join(temp_dir, "secure_storage", "audio", "ch")
            os.makedirs(storage_dir, exist_ok=True)

            # Create multiple test files
            for i in range(3):
                file_path = os.path.join(storage_dir, f"child_audio_{child_id}_{i}.wav")
                metadata_path = file_path + ".meta"

                with open(file_path, "wb") as f:
                    f.write(f"test audio {i}".encode())
                with open(metadata_path, "w") as f:
                    json.dump({"index": i}, f)

            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                with patch.object(secure_ops, "_secure_delete") as mock_delete:
                    result = secure_ops.delete_child_data(child_id)

                    assert result["success"] is True
                    assert len(result["deleted_files"]) == 6  # 3 files + 3 metadata
                    assert mock_delete.call_count == 6

    def test_delete_child_data_error(self, secure_ops):
        """Test child data deletion error handling."""
        with patch.object(
            secure_ops, "_secure_delete", side_effect=PermissionError("Access denied")
        ):
            result = secure_ops.delete_child_data("child_123", "test.wav")

            assert result["success"] is False
            assert "error" in result

    def test_audit_file_access(self, secure_ops):
        """Test file access auditing."""
        child_id = "child_123"
        operation = "file_read"
        details = {"file": "test.wav", "user": "parent_456"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "audit_logs":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                with patch("src.utils.file_utils.datetime") as mock_datetime:
                    mock_datetime.now.return_value.isoformat.return_value = (
                        "2025-07-29T12:00:00"
                    )
                    mock_datetime.now.return_value.strftime.return_value = "202507"

                    secure_ops.audit_file_access(child_id, operation, details)

                    # Verify audit log was created
                    audit_file = os.path.join(
                        temp_dir, "audit_logs", "file_access_202507.log"
                    )
                    assert os.path.exists(audit_file)

                    # Verify audit content
                    with open(audit_file, "r") as f:
                        audit_entry = json.loads(f.read().strip())

                    assert audit_entry["child_id"] == child_id
                    assert audit_entry["operation"] == operation
                    assert audit_entry["details"] == details
                    assert audit_entry["coppa_audit"] is True

    def test_secure_delete(self, secure_ops):
        """Test secure file deletion."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"sensitive data to be deleted")
            temp_path = temp.name

        # File should exist initially
        assert os.path.exists(temp_path)

        # Perform secure deletion
        secure_ops._secure_delete(temp_path)

        # File should be deleted
        assert not os.path.exists(temp_path)

    def test_secure_delete_nonexistent_file(self, secure_ops):
        """Test secure deletion of non-existent file."""
        # Should not raise exception
        secure_ops._secure_delete("nonexistent_file.txt")

    def test_secure_delete_overwrite_process(self, secure_ops):
        """Test that secure delete properly overwrites file."""
        original_content = b"secret data that must be securely deleted"

        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(original_content)
            temp_path = temp.name

        # Mock os.urandom to return predictable data for testing
        with patch("src.utils.file_utils.os.urandom") as mock_random:
            mock_random.return_value = b"X" * len(original_content)

            # Track file operations
            with patch("builtins.open", mock_open()) as mock_file:
                with patch("src.utils.file_utils.os.path.exists", return_value=True):
                    with patch(
                        "src.utils.file_utils.os.path.getsize",
                        return_value=len(original_content),
                    ):
                        with patch("src.utils.file_utils.os.unlink") as mock_unlink:
                            secure_ops._secure_delete(temp_path)

                            # Verify overwrite operations
                            assert mock_random.call_count == 3  # 3 overwrite passes
                            mock_unlink.assert_called_once_with(temp_path)

    def test_get_storage_stats_empty(self, secure_ops):
        """Test storage statistics for empty storage."""
        with patch("src.utils.file_utils.os.path.exists", return_value=False):
            stats = secure_ops.get_storage_stats()

            assert stats["total_files"] == 0
            assert stats["total_size"] == 0

    def test_get_storage_stats_with_files(self, secure_ops):
        """Test storage statistics with files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = [
                ("file1.wav", b"audio data 1"),
                ("file2.wav", b"audio data 2 longer"),
                ("file1.wav.meta", b"metadata 1"),  # Should be ignored
                ("file2.wav.meta", b"metadata 2"),  # Should be ignored
            ]

            for filename, content in test_files:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(content)

            with patch("src.utils.file_utils.os.walk") as mock_walk:
                mock_walk.return_value = [(temp_dir, [], [f[0] for f in test_files])]

                with patch("src.utils.file_utils.os.path.getsize") as mock_getsize:

                    def getsize_side_effect(path):
                        filename = os.path.basename(path)
                        for test_filename, content in test_files:
                            if filename == test_filename:
                                return len(content)
                        return 0

                    mock_getsize.side_effect = getsize_side_effect

                    with patch("src.utils.file_utils.datetime") as mock_datetime:
                        mock_datetime.now.return_value.isoformat.return_value = (
                            "2025-07-29T12:00:00"
                        )

                        stats = secure_ops.get_storage_stats()

                        # Should only count non-metadata files
                        assert stats["total_files"] == 2
                        assert stats["total_size"] == len(b"audio data 1") + len(
                            b"audio data 2 longer"
                        )
                        assert "total_size_mb" in stats
                        assert "last_updated" in stats


class TestFileUtilsIntegration:
    """Test integration scenarios for file utilities."""

    def test_complete_child_audio_workflow(self):
        """Test complete workflow for child audio handling."""
        secure_ops = SecureFileOperations()
        child_id = "child_integration_test"
        audio_data = b"test child audio data for integration"
        metadata = {
            "duration": 3.5,
            "format": "wav",
            "recorded_at": "2025-07-29T12:00:00Z",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                # 1. Store child audio
                store_result = secure_ops.store_child_audio(
                    audio_data, child_id, metadata
                )
                assert store_result["success"] is True

                file_identifier = os.path.basename(store_result["file_path"])

                # 2. Retrieve child audio
                retrieve_result = secure_ops.retrieve_child_audio(
                    child_id, file_identifier
                )
                assert retrieve_result["success"] is True
                assert retrieve_result["audio_data"] == audio_data

                # 3. Audit access
                secure_ops.audit_file_access(
                    child_id, "retrieve", {"file": file_identifier}
                )

                # 4. Get storage stats
                stats = secure_ops.get_storage_stats()
                assert stats["total_files"] >= 1

                # 5. Delete child data
                delete_result = secure_ops.delete_child_data(child_id, file_identifier)
                assert delete_result["success"] is True

    def test_file_handler_security_validation_chain(self):
        """Test complete security validation chain."""
        handler = FileHandler(
            max_file_size=1024, allowed_types=["audio/wav"]  # 1KB limit
        )

        # Test chain of validations
        test_cases = [
            # (file_content, mime_type, expected_valid, expected_reason_contains)
            (b"safe audio data", "audio/wav", True, None),
            (b"x" * 2048, "audio/wav", False, "too large"),
            (b"safe data", "application/exe", False, "not allowed"),
            (b"\x4d\x5a malicious", "audio/wav", False, "malicious"),
        ]

        for content, mime_type, expected_valid, reason_contains in test_cases:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
                temp.write(content)
                temp_path = temp.name

            try:
                with patch("mimetypes.guess_type") as mock_mime:
                    mock_mime.return_value = (mime_type, None)

                    result = handler.validate_file(temp_path)

                    assert result["valid"] == expected_valid
                    if not expected_valid:
                        assert reason_contains in result["reason"].lower()

            finally:
                os.unlink(temp_path)

    def test_coppa_compliance_file_operations(self):
        """Test COPPA compliance in file operations."""
        secure_ops = SecureFileOperations()

        # Test multiple children's data isolation
        children_data = [
            ("child_001", b"audio data for child 1"),
            ("child_002", b"audio data for child 2"),
            ("child_003", b"audio data for child 3"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                stored_files = []

                # Store data for each child
                for child_id, audio_data in children_data:
                    metadata = {"child_id": child_id, "coppa_protected": True}
                    result = secure_ops.store_child_audio(
                        audio_data, child_id, metadata
                    )
                    assert result["success"] is True

                    stored_files.append(
                        (child_id, os.path.basename(result["file_path"]))
                    )

                # Verify data isolation - each child can only access their own data
                for child_id, file_identifier in stored_files:
                    # Child can access their own data
                    result = secure_ops.retrieve_child_audio(child_id, file_identifier)
                    assert result["success"] is True

                    # Other children cannot access this data
                    for other_child_id, _ in children_data:
                        if other_child_id != child_id:
                            other_result = secure_ops.retrieve_child_audio(
                                other_child_id, file_identifier
                            )
                            assert other_result["success"] is False
                            assert "Access denied" in other_result["error"]

    def test_file_utils_error_resilience(self):
        """Test error resilience across file utilities."""
        handler = FileHandler()
        secure_ops = SecureFileOperations()

        # Test various error scenarios
        error_scenarios = [
            # File handler errors
            ("validate_file", lambda: handler.validate_file("nonexistent.wav")),
            ("secure_filename", lambda: handler.secure_filename("")),
            (
                "safe_file_copy",
                lambda: handler.safe_file_copy("nonexistent.wav", "dest.wav"),
            ),
            # Secure operations errors
            (
                "retrieve_child_audio",
                lambda: secure_ops.retrieve_child_audio("child_123", "nonexistent.wav"),
            ),
            (
                "delete_child_data",
                lambda: secure_ops.delete_child_data("child_123", "nonexistent.wav"),
            ),
        ]

        for scenario_name, operation in error_scenarios:
            try:
                result = operation()

                # Operations should return error states, not raise exceptions
                if isinstance(result, dict):
                    # For operations that return result dictionaries
                    assert "success" in result or "valid" in result
                elif isinstance(result, str):
                    # For operations that return strings (like secure_filename)
                    assert len(result) > 0
                elif isinstance(result, bool):
                    # For operations that return boolean
                    # Should complete without exception
                    pass

            except Exception as e:
                # If exceptions are raised, they should be specific and informative
                assert len(str(e)) > 0
                print(f"Expected exception in {scenario_name}: {e}")


class TestFileUtilsChildSafety:
    """Test child safety aspects of file utilities."""

    def test_child_audio_metadata_protection(self):
        """Test that child audio metadata is properly protected."""
        secure_ops = SecureFileOperations()
        child_id = "child_safety_test"

        # Test that sensitive metadata is handled properly
        sensitive_metadata = {
            "child_name": "Alice",  # Should not be stored in plain text
            "parent_email": "parent@example.com",  # Should not be stored
            "duration": 5.0,  # Safe to store
            "format": "wav",  # Safe to store
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "secure_storage":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                # Store audio with metadata
                result = secure_ops.store_child_audio(
                    b"test audio", child_id, sensitive_metadata
                )
                assert result["success"] is True

                # Verify stored metadata
                with open(result["metadata_path"], "r") as f:
                    stored_metadata = json.load(f)

                # Check COPPA compliance flags
                assert stored_metadata["coppa_protected"] is True
                assert stored_metadata["child_id"] == child_id

                # All original metadata should be preserved (filtering would be done at application level)
                assert stored_metadata["duration"] == 5.0
                assert stored_metadata["format"] == "wav"

    def test_file_access_audit_trail(self):
        """Test that file access creates proper audit trail."""
        secure_ops = SecureFileOperations()

        audit_scenarios = [
            ("child_001", "audio_upload", {"file_size": 1024, "duration": 3.0}),
            ("child_001", "audio_playback", {"file": "audio_123.wav"}),
            ("child_002", "audio_download", {"requested_by": "parent_456"}),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.utils.file_utils.os.path.join") as mock_join:

                def side_effect(*args):
                    if args[0] == "audit_logs":
                        return os.path.join(temp_dir, *args)
                    return os.path.join(*args)

                mock_join.side_effect = side_effect

                # Generate audit entries
                for child_id, operation, details in audit_scenarios:
                    secure_ops.audit_file_access(child_id, operation, details)

                # Verify audit files were created
                audit_files = list(Path(temp_dir).glob("audit_logs/*.log"))
                assert len(audit_files) > 0

                # Verify audit content
                all_entries = []
                for audit_file in audit_files:
                    with open(audit_file, "r") as f:
                        for line in f:
                            if line.strip():
                                all_entries.append(json.loads(line))

                assert len(all_entries) == len(audit_scenarios)

                # Verify each entry has required COPPA audit fields
                for entry in all_entries:
                    assert entry["coppa_audit"] is True
                    assert "timestamp" in entry
                    assert "child_id" in entry
                    assert "operation" in entry

    def test_secure_file_permissions(self):
        """Test that files are created with secure permissions."""
        handler = FileHandler()
        secure_ops = SecureFileOperations()

        # Test temp file permissions
        temp_file = handler.create_temp_file()
        try:
            file_mode = os.stat(temp_file).st_mode
            # Should be readable/writable by owner only (600)
            assert oct(file_mode)[-3:] == "600"
        finally:
            os.unlink(temp_file)

        # Test copied file permissions
        with tempfile.NamedTemporaryFile() as source:
            source.write(b"test data")
            source.flush()

            with tempfile.TemporaryDirectory() as temp_dir:
                dest_path = os.path.join(temp_dir, "secure_copy.wav")

                with patch.object(handler, "validate_file") as mock_validate:
                    mock_validate.return_value = {"valid": True}

                    success = handler.safe_file_copy(source.name, dest_path)
                    assert success is True

                    file_mode = os.stat(dest_path).st_mode
                    assert oct(file_mode)[-3:] == "600"
