"""
Production File Storage Adapter - Legacy Compatibility Module  
============================================================
File storage adapter that wraps the existing production file storage.
"""

from .production_file_storage import *


class ProductionFileStorageAdapter:
    """Production file storage adapter with enterprise features."""
    
    def __init__(self):
        """Initialize the production file storage adapter."""
        # Use default configuration for production
        from src.infrastructure.storage.production_file_storage import (
            StorageConfig, 
            StorageProvider, 
            ProductionFileStorage
        )
        
        # Default configuration - users can override via environment variables
        default_config = StorageConfig(
            provider=StorageProvider.AWS_S3,
            bucket_name="ai-teddy-bear-storage",
            region="us-east-1"
        )
        
        self.storage = ProductionFileStorage([default_config])
    
    async def upload_file(self, file_data: bytes, metadata: dict) -> dict:
        """Upload file with metadata."""
        from src.infrastructure.storage.production_file_storage import FileMetadata, FileType
        
        # Convert metadata dict to FileMetadata object
        file_metadata = FileMetadata(
            file_id=metadata.get("file_id", ""),
            filename=metadata.get("filename", ""),
            content_type=metadata.get("content_type", "application/octet-stream"),
            file_size=len(file_data),
            file_type=FileType(metadata.get("file_type", "other")),
            user_id=metadata.get("user_id"),
            tags=metadata.get("tags", {})
        )
        
        result = await self.storage.upload_file(file_data, file_metadata)
        
        return {
            "success": result.success,
            "storage_url": result.storage_url,
            "cdn_url": result.cdn_url,
            "error": result.error_message,
            "upload_time": result.upload_time,
            "bytes_transferred": result.bytes_transferred
        }
    
    async def download_file(self, file_path: str) -> dict:
        """Download file by path."""
        result = await self.storage.download_file(file_path)
        
        return {
            "success": result.success,
            "content": result.content,
            "content_type": result.content_type,
            "file_size": result.file_size,
            "error": result.error_message,
            "download_time": result.download_time
        }
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file by path."""
        return await self.storage.delete_file(file_path)
    
    async def list_files(self, prefix: str = "", limit: int = 1000) -> dict:
        """List files with optional prefix."""
        files, next_token = await self.storage.list_files(prefix, limit)
        
        return {
            "files": [
                {
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "file_size": f.file_size,
                    "content_type": f.content_type,
                    "storage_path": f.storage_path,
                    "created_at": f.created_at.isoformat(),
                    "user_id": f.user_id,
                    "tags": f.tags
                }
                for f in files
            ],
            "next_token": next_token
        }
    
    async def get_file_metadata(self, file_path: str) -> dict:
        """Get file metadata."""
        metadata = await self.storage.get_file_metadata(file_path)
        
        if metadata:
            return {
                "file_id": metadata.file_id,
                "filename": metadata.filename,
                "file_size": metadata.file_size,
                "content_type": metadata.content_type,
                "storage_path": metadata.storage_path,
                "created_at": metadata.created_at.isoformat(),
                "user_id": metadata.user_id,
                "tags": metadata.tags,
                "checksum_md5": metadata.checksum_md5,
                "checksum_sha256": metadata.checksum_sha256
            }
        
        return None
    
    async def generate_presigned_url(self, file_path: str, expiration: int = 3600) -> str:
        """Generate presigned URL for direct access."""
        return await self.storage.generate_presigned_url(file_path, expiration)
    
    async def health_check(self) -> dict:
        """Perform health check on storage system."""
        return await self.storage.health_check()


# Legacy alias for backward compatibility
production_file_storage_adapter = ProductionFileStorageAdapter