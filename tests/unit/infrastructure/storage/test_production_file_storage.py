"""
Tests for Production File Storage.
"""

import pytest
import os
import json
import tempfile
from datetime import datetime
import aioboto3
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.infrastructure.storage.production_file_storage import (
    StorageProvider,
    StorageClass,
    FileType,
    FileCategory,
    LoadBalancingStrategy,
    StorageConfig,
    FileMetadata,
    UploadResult,
    FileStorageMetrics,
    AWSS3Provider,
    MinIOProvider,
    LocalFileSystemProvider,
)


class TestStorageConfig:
    """Test storage configuration."""

    def test_storage_config_creation(self):
        """Test storage config creation."""
        config = StorageConfig(
            provider=StorageProvider.AWS_S3,
            bucket_name="test-bucket",
            region="us-east-1",
            access_key="test-key",
            secret_key="test-secret",
        )

        assert config.provider == StorageProvider.AWS_S3
        assert config.bucket_name == "test-bucket"
        assert config.region == "us-east-1"
        assert config.max_concurrent_uploads == 10
        assert config.enable_encryption is True

    def test_storage_config_defaults(self):
        """Test storage config default values."""
        config = StorageConfig(
            provider=StorageProvider.AZURE_BLOB, bucket_name="test-container"
        )

        assert config.region == "us-east-1"
        assert config.multipart_threshold == 8 * 1024 * 1024
        assert config.transfer_timeout == 300
        assert config.enable_versioning is True


class TestFileMetadata:
    """Test file metadata functionality."""

    def test_file_metadata_creation(self):
        """Test file metadata creation."""
        metadata = FileMetadata(
            file_id="file-123",
            filename="test.jpg",
            content_type="image/jpeg",
            file_size=1024,
            file_type=FileType.IMAGE,
            user_id="user-456",
        )

        assert metadata.file_id == "file-123"
        assert metadata.filename == "test.jpg"
        assert metadata.content_type == "image/jpeg"
        assert metadata.file_size == 1024
        assert metadata.file_type == FileType.IMAGE
        assert metadata.storage_class == StorageClass.STANDARD
        assert metadata.encrypted is False
        assert isinstance(metadata.created_at, datetime)

    def test_file_metadata_with_tags(self):
        """Test file metadata with tags."""
        metadata = FileMetadata(
            file_id="file-123",
            filename="test.mp3",
            content_type="audio/mpeg",
            file_size=2048,
            file_type=FileType.AUDIO,
            tags={"category": "story", "age_group": "5-8"},
        )

        assert metadata.tags["category"] == "story"
        assert metadata.tags["age_group"] == "5-8"


class TestUploadResult:
    """Test upload result functionality."""

    def test_upload_result_success(self):
        """Test successful upload result."""
        metadata = FileMetadata(
            file_id="file-123",
            filename="test.txt",
            content_type="text/plain",
            file_size=100,
            file_type=FileType.DOCUMENT,
        )

        result = UploadResult(
            success=True,
            file_metadata=metadata,
            storage_url="s3://bucket/path/file-123",
            cdn_url="https://cdn.example.com/file-123",
            upload_time=1.5,
            bytes_transferred=100,
        )

        assert result.success is True
        assert result.file_metadata == metadata
        assert result.storage_url == "s3://bucket/path/file-123"
        assert result.upload_time == 1.5
        assert result.error_message == ""

    def test_upload_result_failure(self):
        """Test failed upload result."""
        result = UploadResult(
            success=False, error_message="Upload failed", upload_time=0.5
        )

        assert result.success is False
        assert result.error_message == "Upload failed"
        assert result.file_metadata is None


class TestFileStorageMetrics:
    """Test file storage metrics."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = FileStorageMetrics()

        assert metrics.files_uploaded == 0
        assert metrics.files_downloaded == 0
        assert metrics.bytes_uploaded == 0
        assert metrics.upload_success_rate == 0.0

    def test_upload_success_rate_calculation(self):
        """Test upload success rate calculation."""
        metrics = FileStorageMetrics(files_uploaded=8, upload_failures=2)

        assert metrics.upload_success_rate == 80.0

    def test_upload_success_rate_no_uploads(self):
        """Test upload success rate with no uploads."""
        metrics = FileStorageMetrics()

        assert metrics.upload_success_rate == 0.0


class TestLocalFileSystemProvider:
    """Test local filesystem provider."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def config(self, temp_dir):
        """Create storage config for local filesystem."""
        return StorageConfig(
            provider=StorageProvider.LOCAL_FILESYSTEM, bucket_name=temp_dir
        )

    @pytest.fixture
    def provider(self, config):
        """Create local filesystem provider."""
        return LocalFileSystemProvider(config)

    @pytest.mark.asyncio
    async def test_upload_file_success(self, provider):
        """Test successful file upload."""
        file_data = b"test file content"
        metadata = FileMetadata(
            file_id="test-123",
            filename="test.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
            user_id="user-456",
        )

        result = await provider.upload_file(file_data, metadata)

        assert result.success is True
        assert result.file_metadata.file_id == "test-123"
        assert result.bytes_transferred == len(file_data)
        assert result.upload_time > 0
        assert result.storage_url.startswith("file://")

    @pytest.mark.asyncio
    async def test_upload_file_with_metadata(self, provider):
        """Test file upload with metadata persistence."""
        file_data = b"test content with metadata"
        metadata = FileMetadata(
            file_id="meta-test-123",
            filename="metadata_test.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
            user_id="user-789",
            tags={"category": "test", "priority": "high"},
        )

        result = await provider.upload_file(file_data, metadata)

        assert result.success is True

        # Check that metadata file was created
        storage_path = result.file_metadata.storage_path
        full_path = os.path.join(provider.base_path, storage_path)
        metadata_path = full_path + ".metadata.json"

        assert os.path.exists(metadata_path)

        # Verify metadata content
        with open(metadata_path, "r") as f:
            saved_metadata = json.load(f)

        assert saved_metadata["file_id"] == "meta-test-123"
        assert saved_metadata["user_id"] == "user-789"
        assert saved_metadata["tags"]["category"] == "test"

    @pytest.mark.asyncio
    async def test_download_file_success(self, provider):
        """Test successful file download."""
        # First upload a file
        file_data = b"download test content"
        metadata = FileMetadata(
            file_id="download-123",
            filename="download_test.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
        )

        upload_result = await provider.upload_file(file_data, metadata)
        assert upload_result.success is True

        # Now download it
        download_result = await provider.download_file(
            upload_result.file_metadata.storage_path
        )

        assert download_result.success is True
        assert download_result.content == file_data
        assert download_result.content_type == "text/plain"
        assert download_result.file_size == len(file_data)
        assert download_result.download_time > 0

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, provider):
        """Test download of non-existent file."""
        result = await provider.download_file("non/existent/file.txt")

        assert result.success is False
        assert "File not found" in result.error_message
        assert result.content is None

    @pytest.mark.asyncio
    async def test_delete_file_success(self, provider):
        """Test successful file deletion."""
        # Upload a file first
        file_data = b"delete test content"
        metadata = FileMetadata(
            file_id="delete-123",
            filename="delete_test.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
        )

        upload_result = await provider.upload_file(file_data, metadata)
        assert upload_result.success is True

        # Verify file exists
        storage_path = upload_result.file_metadata.storage_path
        full_path = os.path.join(provider.base_path, storage_path)
        assert os.path.exists(full_path)

        # Delete the file
        delete_success = await provider.delete_file(storage_path)

        assert delete_success is True
        assert not os.path.exists(full_path)

    @pytest.mark.asyncio
    async def test_list_files(self, provider):
        """Test file listing."""
        # Upload multiple files
        files_data = [
            (b"content1", "file1.txt"),
            (b"content2", "file2.txt"),
            (b"content3", "file3.jpg"),
        ]

        for content, filename in files_data:
            metadata = FileMetadata(
                file_id=str(uuid4()),
                filename=filename,
                content_type=(
                    "text/plain" if filename.endswith(".txt") else "image/jpeg"
                ),
                file_size=len(content),
                file_type=(
                    FileType.DOCUMENT if filename.endswith(".txt") else FileType.IMAGE
                ),
            )

            result = await provider.upload_file(content, metadata)
            assert result.success is True

        # List files
        files, continuation_token = await provider.list_files()

        assert len(files) == 3
        assert continuation_token is None

        # Check file metadata
        filenames = [f.filename for f in files]
        assert "file1.txt" in filenames
        assert "file2.txt" in filenames
        assert "file3.jpg" in filenames

    @pytest.mark.asyncio
    async def test_list_files_with_prefix(self, provider):
        """Test file listing with prefix filter."""
        # Upload files in different directories
        test_files = [
            ("users/user1/file1.txt", b"user1 content"),
            ("users/user2/file2.txt", b"user2 content"),
            ("public/file3.txt", b"public content"),
        ]

        for path, content in test_files:
            # Create directory structure
            full_path = os.path.join(provider.base_path, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(content)

        # List files with prefix
        files, _ = await provider.list_files(prefix="users/user1")

        assert len(files) >= 1
        user1_files = [f for f in files if "user1" in f.storage_path]
        assert len(user1_files) >= 1

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, provider):
        """Test file metadata retrieval."""
        # Upload a file with metadata
        file_data = b"metadata retrieval test"
        metadata = FileMetadata(
            file_id="metadata-123",
            filename="metadata_test.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
            user_id="user-999",
            tags={"test": "metadata"},
        )

        upload_result = await provider.upload_file(file_data, metadata)
        assert upload_result.success is True

        # Retrieve metadata
        retrieved_metadata = await provider.get_file_metadata(
            upload_result.file_metadata.storage_path
        )

        assert retrieved_metadata is not None
        assert retrieved_metadata.file_id == "metadata-123"
        assert retrieved_metadata.filename == "metadata_test.txt"
        assert retrieved_metadata.user_id == "user-999"
        assert retrieved_metadata.tags["test"] == "metadata"

    @pytest.mark.asyncio
    async def test_get_file_metadata_not_found(self, provider):
        """Test metadata retrieval for non-existent file."""
        metadata = await provider.get_file_metadata("non/existent/file.txt")

        assert metadata is None

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, provider):
        """Test presigned URL generation."""
        file_path = "test/file.txt"
        url = await provider.generate_presigned_url(file_path)

        assert url.startswith("file://")
        assert file_path in url

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, provider):
        """Test health check when healthy."""
        health = await provider.health_check()

        assert health["healthy"] is True
        assert health["provider"] == "local_filesystem"
        assert health["base_path"] == provider.base_path
        assert health["error"] is None

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, provider):
        """Test health check when unhealthy."""
        # Make base path read-only to simulate failure
        original_base_path = provider.base_path
        provider.base_path = "/invalid/readonly/path"

        health = await provider.health_check()

        assert health["healthy"] is False
        assert health["provider"] == "local_filesystem"
        assert health["error"] is not None

        # Restore original path
        provider.base_path = original_base_path

    def test_calculate_checksums(self, provider):
        """Test checksum calculation."""
        test_data = b"test data for checksum"
        md5_hash, sha256_hash = provider._calculate_checksums(test_data)

        assert isinstance(md5_hash, str)
        assert isinstance(sha256_hash, str)
        assert len(md5_hash) == 32  # MD5 hex length
        assert len(sha256_hash) == 64  # SHA256 hex length

    def test_get_storage_path(self, provider):
        """Test storage path generation."""
        metadata = FileMetadata(
            file_id="path-test-123",
            filename="test.txt",
            content_type="text/plain",
            file_size=100,
            file_type=FileType.DOCUMENT,
            user_id="user-456",
            created_at=datetime(2023, 12, 25, 10, 30, 0),
        )

        path = provider._get_storage_path(metadata)

        assert "users/user-456" in path
        assert "document" in path
        assert "2023/12/25" in path
        assert "path-test-123" in path

    def test_get_storage_path_no_user(self, provider):
        """Test storage path generation without user ID."""
        metadata = FileMetadata(
            file_id="public-123",
            filename="public.txt",
            content_type="text/plain",
            file_size=100,
            file_type=FileType.DOCUMENT,
            created_at=datetime(2023, 12, 25, 10, 30, 0),
        )

        path = provider._get_storage_path(metadata)

        assert "public" in path
        assert "document" in path
        assert "2023/12/25" in path


class TestAWSS3Provider:
    """Test AWS S3 provider."""

    @pytest.fixture
    def config(self):
        """Create S3 storage config."""
        return StorageConfig(
            provider=StorageProvider.AWS_S3,
            bucket_name="test-bucket",
            region="us-east-1",
            access_key="test-key",
            secret_key="test-secret",
        )

    @pytest.fixture
    def provider(self, config):
        """Create S3 provider."""
        return AWSS3Provider(config)

    @pytest.mark.asyncio
    async def test_get_s3_client(self, provider):
        """Test S3 client creation."""
        with patch("aioboto3.Session", autospec=True) as mock_session:
            mock_client = AsyncMock(spec=aioboto3.Session)
            mock_session.return_value.client.return_value = mock_client

            client = await provider._get_s3_client()

            assert client == mock_client
            mock_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_success(self, provider):
        """Test successful S3 upload."""
        file_data = b"S3 test content"
        metadata = FileMetadata(
            file_id="s3-test-123",
            filename="s3_test.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
        )

        # Mock S3 client
        mock_s3_client = AsyncMock(spec=aioboto3.Session)
        mock_s3_client.put_object = AsyncMock(spec=aioboto3.Session.put_object)

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            with patch.object(
                provider.circuit_breaker, "call", new_callable=AsyncMock
            ) as mock_call:
                mock_call.return_value = None

                result = await provider.upload_file(file_data, metadata)

                assert result.success is True
                assert result.file_metadata.file_id == "s3-test-123"
                assert result.storage_url.startswith("s3://")
                assert result.bytes_transferred == len(file_data)
                mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_with_encryption(self, provider):
        """Test S3 upload with encryption."""
        provider.config.enable_encryption = True
        provider.config.encryption_key = "test-encryption-key"

        file_data = b"encrypted content"
        metadata = FileMetadata(
            file_id="encrypted-123",
            filename="encrypted.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
        )

        mock_s3_client = AsyncMock(spec=aioboto3.Session)

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            with patch.object(
                provider.circuit_breaker, "call", new_callable=AsyncMock
            ) as mock_call:
                await provider.upload_file(file_data, metadata)

                # Verify encryption parameters were passed
                call_args = mock_call.call_args[1]
                assert "ServerSideEncryption" in call_args
                assert call_args["ServerSideEncryption"] == "AES256"

    @pytest.mark.asyncio
    async def test_upload_file_failure(self, provider):
        """Test S3 upload failure."""
        file_data = b"fail test content"
        metadata = FileMetadata(
            file_id="fail-123",
            filename="fail.txt",
            content_type="text/plain",
            file_size=len(file_data),
            file_type=FileType.DOCUMENT,
        )

        mock_s3_client = AsyncMock(spec=aioboto3.Session)

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            with patch.object(
                provider.circuit_breaker, "call", side_effect=Exception("S3 error")
            ):
                result = await provider.upload_file(file_data, metadata)

                assert result.success is False
                assert "S3 error" in result.error_message

    @pytest.mark.asyncio
    async def test_download_file_success(self, provider):
        """Test successful S3 download."""
        file_path = "test/file.txt"
        expected_content = b"downloaded content"

        mock_s3_client = AsyncMock(spec=aioboto3.Session)
        mock_response = {
            "Body": AsyncMock(spec=True),
            "ContentType": "text/plain",
            "ContentLength": len(expected_content),
        }
        mock_response["Body"].read = AsyncMock(return_value=expected_content)

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            with patch.object(
                provider.circuit_breaker, "call", return_value=mock_response
            ):
                result = await provider.download_file(file_path)

                assert result.success is True
                assert result.content == expected_content
                assert result.content_type == "text/plain"
                assert result.file_size == len(expected_content)

    @pytest.mark.asyncio
    async def test_download_file_with_range(self, provider):
        """Test S3 download with range header."""
        file_path = "test/file.txt"
        range_header = "bytes=0-99"

        mock_s3_client = AsyncMock(spec=aioboto3.Session)
        mock_response = {
            "Body": AsyncMock(spec=True),
            "ContentType": "text/plain",
            "ContentLength": 100,
        }
        mock_response["Body"].read = AsyncMock(return_value=b"partial content")

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            with patch.object(
                provider.circuit_breaker, "call", return_value=mock_response
            ) as mock_call:
                result = await provider.download_file(file_path, range_header)

                assert result.success is True
                # Verify range header was passed
                call_args = mock_call.call_args[1]
                assert call_args["Range"] == range_header

    @pytest.mark.asyncio
    async def test_delete_file_success(self, provider):
        """Test successful S3 file deletion."""
        file_path = "test/delete_me.txt"

        mock_s3_client = AsyncMock(spec=aioboto3.Session)

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            with patch.object(
                provider.circuit_breaker, "call", new_callable=AsyncMock
            ) as mock_call:
                result = await provider.delete_file(file_path)

                assert result is True
                mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_files_success(self, provider):
        """Test successful S3 file listing."""
        mock_s3_client = AsyncMock(spec=aioboto3.Session)
        mock_response = {
            "Contents": [
                {"Key": "test/file1.txt", "Size": 100, "LastModified": datetime.now()},
                {"Key": "test/file2.txt", "Size": 200, "LastModified": datetime.now()},
            ],
            "NextContinuationToken": "next-token",
        }

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            with patch.object(
                provider.circuit_breaker, "call", return_value=mock_response
            ):
                files, next_token = await provider.list_files(prefix="test/", limit=10)

                assert len(files) == 2
                assert next_token == "next-token"
                assert files[0].storage_path == "test/file1.txt"
                assert files[1].file_size == 200

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, provider):
        """Test presigned URL generation."""
        file_path = "test/presigned.txt"
        expected_url = (
            "https://s3.amazonaws.com/bucket/test/presigned.txt?signature=..."
        )

        mock_s3_client = AsyncMock(spec=aioboto3.Session)
        mock_s3_client.generate_presigned_url = AsyncMock(
            return_value=expected_url, spec=aioboto3.Session.generate_presigned_url
        )

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            url = await provider.generate_presigned_url(file_path, expiration=3600)

            assert url == expected_url
            mock_s3_client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, provider):
        """Test S3 health check when healthy."""
        mock_s3_client = AsyncMock(spec=True)
        mock_s3_client.head_bucket = AsyncMock(spec=True)

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            health = await provider.health_check()

            assert health["healthy"] is True
            assert health["provider"] == "aws_s3"
            assert health["bucket"] == "test-bucket"
            assert health["region"] == "us-east-1"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, provider):
        """Test S3 health check when unhealthy."""
        mock_s3_client = AsyncMock(spec=True)
        mock_s3_client.head_bucket = AsyncMock(side_effect=Exception("Access denied"))

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            health = await provider.health_check()

            assert health["healthy"] is False
            assert health["provider"] == "aws_s3"
            assert "Access denied" in health["error"]


class TestMinIOProvider:
    """Test MinIO provider (S3-compatible)."""

    @pytest.fixture
    def config(self):
        """Create MinIO storage config."""
        return StorageConfig(
            provider=StorageProvider.MINIO,
            bucket_name="test-bucket",
            endpoint_url="http://localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )

    @pytest.fixture
    def provider(self, config):
        """Create MinIO provider."""
        return MinIOProvider(config)

    @pytest.mark.asyncio
    async def test_health_check_minio(self, provider):
        """Test MinIO-specific health check."""
        mock_s3_client = AsyncMock(spec=True)
        mock_s3_client.head_bucket = AsyncMock(spec=True)

        with patch.object(provider, "_get_s3_client", return_value=mock_s3_client):
            health = await provider.health_check()

            assert health["healthy"] is True
            assert health["provider"] == "minio"
            assert health["bucket"] == "test-bucket"
            assert health["endpoint"] == "http://localhost:9000"


class TestStorageProviderBase:
    """Test storage provider base class functionality."""

    @pytest.fixture
    def config(self):
        """Create basic storage config."""
        return StorageConfig(
            provider=StorageProvider.LOCAL_FILESYSTEM, bucket_name="test"
        )

    @pytest.fixture
    def provider(self, config):
        """Create local filesystem provider for base class testing."""
        return LocalFileSystemProvider(config)

    def test_calculate_checksums(self, provider):
        """Test checksum calculation."""
        test_data = b"checksum test data"
        md5_hash, sha256_hash = provider._calculate_checksums(test_data)

        # Verify hash formats
        assert len(md5_hash) == 32
        assert len(sha256_hash) == 64
        assert all(c in "0123456789abcdef" for c in md5_hash)
        assert all(c in "0123456789abcdef" for c in sha256_hash)

    def test_get_storage_path_organization(self, provider):
        """Test storage path organization."""
        metadata = FileMetadata(
            file_id="org-test-123",
            filename="organization.txt",
            content_type="text/plain",
            file_size=100,
            file_type=FileType.DOCUMENT,
            user_id="user-789",
            created_at=datetime(2023, 6, 15, 14, 30, 0),
        )

        path = provider._get_storage_path(metadata)

        # Verify path structure: users/{user_id}/{file_type}/{date}/{file_id}
        expected_parts = [
            "users",
            "user-789",
            "document",
            "2023",
            "06",
            "15",
            "org-test-123",
        ]
        for part in expected_parts:
            assert part in path

    def test_circuit_breaker_initialization(self, provider):
        """Test circuit breaker initialization."""
        assert provider.circuit_breaker is not None
        assert provider.circuit_breaker.name == "storage_local_filesystem"
        assert provider.circuit_breaker.config.failure_threshold == 5
        assert provider.circuit_breaker.config.recovery_timeout == 60


class TestEnums:
    """Test enum definitions."""

    def test_storage_provider_enum(self):
        """Test StorageProvider enum values."""
        assert StorageProvider.AWS_S3.value == "aws_s3"
        assert StorageProvider.AZURE_BLOB.value == "azure_blob"
        assert StorageProvider.GOOGLE_CLOUD.value == "google_cloud"
        assert StorageProvider.MINIO.value == "minio"
        assert StorageProvider.LOCAL_FILESYSTEM.value == "local_filesystem"

    def test_storage_class_enum(self):
        """Test StorageClass enum values."""
        assert StorageClass.STANDARD.value == "standard"
        assert StorageClass.INFREQUENT_ACCESS.value == "infrequent_access"
        assert StorageClass.ARCHIVE.value == "archive"
        assert StorageClass.DEEP_ARCHIVE.value == "deep_archive"

    def test_file_type_enum(self):
        """Test FileType enum values."""
        assert FileType.AUDIO.value == "audio"
        assert FileType.IMAGE.value == "image"
        assert FileType.VIDEO.value == "video"
        assert FileType.DOCUMENT.value == "document"
        assert FileType.OTHER.value == "other"

    def test_file_category_enum(self):
        """Test FileCategory enum values."""
        assert FileCategory.AUDIO_RECORDINGS.value == "audio_recordings"
        assert FileCategory.USER_UPLOADS.value == "user_uploads"
        assert FileCategory.SYSTEM_LOGS.value == "system_logs"
        assert FileCategory.BACKUPS.value == "backups"
        assert FileCategory.TEMPORARY.value == "temporary"
        assert FileCategory.PROFILE_IMAGES.value == "profile_images"

    def test_load_balancing_strategy_enum(self):
        """Test LoadBalancingStrategy enum values."""
        assert LoadBalancingStrategy.ROUND_ROBIN.value == "round_robin"
        assert LoadBalancingStrategy.LEAST_LATENCY.value == "least_latency"
        assert LoadBalancingStrategy.LEAST_COST.value == "least_cost"
        assert LoadBalancingStrategy.HEALTH_WEIGHTED.value == "health_weighted"
        assert LoadBalancingStrategy.GEOGRAPHIC.value == "geographic"
