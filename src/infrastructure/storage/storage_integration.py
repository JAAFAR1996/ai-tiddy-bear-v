"""
Storage Integration - FastAPI Integration Layer
==============================================
Production integration layer for storage system:
- FastAPI startup/shutdown lifecycle
- File upload/download endpoints
- Health check and metrics endpoints
- Admin management interfaces
- CDN integration
- Background processing
"""

import asyncio
import mimetypes
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
    Depends,
    Form,
    Query,
)
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# Production-safe imports
try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

from .production_file_storage import (
    StorageProvider,
    FileType,
    StorageClass,
    StorageConfig,
    ProductionFileStorage,
    FileMetadata,
    LoadBalancingStrategy,
)
from .storage_health_monitor import StorageHealthMonitor
from ..resilience.fallback_logger import FallbackLogger
from ..messaging.event_bus_integration import EventPublisher
from ..security.admin_security import (
    require_admin_permission,
    AdminPermission,
    SecurityLevel,
    AdminSession
)


class FileUploadRequest(BaseModel):
    """File upload request model."""

    filename: str
    content_type: Optional[str] = None
    file_type: Optional[str] = None
    storage_class: Optional[str] = "standard"
    user_id: Optional[str] = None
    tags: Dict[str, str] = {}
    expires_hours: Optional[int] = None


class FileMetadataResponse(BaseModel):
    """File metadata response model."""

    file_id: str
    filename: str
    content_type: str
    file_size: int
    file_type: str
    storage_provider: str
    storage_path: str
    cdn_url: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None
    tags: Dict[str, str] = {}


class StorageLifecycleManager:
    """Manages storage system lifecycle for FastAPI."""

    def __init__(self):
        self.storage_manager: Optional[ProductionFileStorage] = None
        self.health_monitor: Optional[StorageHealthMonitor] = None
        self.logger = FallbackLogger("storage_lifecycle")

    async def startup(self):
        """Initialize storage system."""
        try:
            # Load configuration from environment
            provider_configs = self._load_provider_configs()

            # Initialize storage manager
            self.storage_manager = ProductionFileStorage(provider_configs)
            await self.storage_manager.initialize()

            # Initialize health monitor
            self.health_monitor = StorageHealthMonitor(self.storage_manager)
            await self.health_monitor.start()

            self.logger.info("Storage system startup completed")

        except Exception as e:
            self.logger.error(f"Storage system startup failed: {str(e)}")
            raise

    async def shutdown(self):
        """Shutdown storage system."""
        try:
            if self.health_monitor:
                await self.health_monitor.stop()

            if self.storage_manager:
                await self.storage_manager.stop()

            self.logger.info("Storage system shutdown completed")

        except Exception as e:
            self.logger.error(f"Storage system shutdown error: {str(e)}")

    def _load_provider_configs(self) -> Dict[StorageProvider, StorageConfig]:
        """Load storage provider configurations from environment."""
        configs = {}

        # AWS S3 Configuration
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            configs[StorageProvider.AWS_S3] = StorageConfig(
                provider=StorageProvider.AWS_S3,
                bucket_name=os.getenv("AWS_S3_BUCKET", "ai-teddy-bear-storage"),
                region=os.getenv("AWS_REGION", "us-east-1"),
                access_key=os.getenv("AWS_ACCESS_KEY_ID"),
                secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                enable_encryption=os.getenv("AWS_S3_ENCRYPTION", "true").lower()
                == "true",
                cdn_domain=os.getenv("AWS_CLOUDFRONT_DOMAIN"),
            )

        # Azure Blob Configuration
        if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
            configs[StorageProvider.AZURE_BLOB] = StorageConfig(
                provider=StorageProvider.AZURE_BLOB,
                bucket_name=os.getenv("AZURE_CONTAINER_NAME", "ai-teddy-bear-storage"),
                connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
                enable_encryption=os.getenv("AZURE_BLOB_ENCRYPTION", "true").lower()
                == "true",
                cdn_domain=os.getenv("AZURE_CDN_DOMAIN"),
            )

        # MinIO Configuration
        if os.getenv("MINIO_ENDPOINT"):
            configs[StorageProvider.MINIO] = StorageConfig(
                provider=StorageProvider.MINIO,
                bucket_name=os.getenv("MINIO_BUCKET", "ai-teddy-bear-storage"),
                endpoint_url=os.getenv("MINIO_ENDPOINT"),
                access_key=os.getenv("MINIO_ACCESS_KEY"),
                secret_key=os.getenv("MINIO_SECRET_KEY"),
                enable_encryption=False,  # MinIO handles encryption internally
            )

        # Local Filesystem (for development)
        if os.getenv("LOCAL_STORAGE_PATH") or not configs:
            configs[StorageProvider.LOCAL_FILESYSTEM] = StorageConfig(
                provider=StorageProvider.LOCAL_FILESYSTEM,
                bucket_name=os.getenv("LOCAL_STORAGE_PATH", "./storage"),
                enable_encryption=False,
            )

        return configs


# Global lifecycle manager
lifecycle_manager = StorageLifecycleManager()


@asynccontextmanager
async def storage_lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI storage integration."""
    # Startup
    await lifecycle_manager.startup()

    try:
        yield
    finally:
        # Shutdown
        await lifecycle_manager.shutdown()


def get_storage_manager() -> ProductionFileStorage:
    """Dependency to get storage manager."""
    if not lifecycle_manager.storage_manager:
        raise HTTPException(status_code=503, detail="Storage system not initialized")
    return lifecycle_manager.storage_manager


def get_health_monitor() -> StorageHealthMonitor:
    """Dependency to get health monitor."""
    if not lifecycle_manager.health_monitor:
        raise HTTPException(status_code=503, detail="Health monitor not initialized")
    return lifecycle_manager.health_monitor


def determine_file_type(filename: str, content_type: str) -> FileType:
    """Determine file type from filename and content type."""
    if content_type:
        if content_type.startswith("image/"):
            return FileType.IMAGE
        elif content_type.startswith("audio/"):
            return FileType.AUDIO
        elif content_type.startswith("video/"):
            return FileType.VIDEO
        elif content_type in ["application/pdf", "text/plain", "application/msword"]:
            return FileType.DOCUMENT

    # Fallback to extension-based detection
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if ext in ["jpg", "jpeg", "png", "gif", "webp", "bmp"]:
        return FileType.IMAGE
    elif ext in ["mp3", "wav", "ogg", "flac", "m4a"]:
        return FileType.AUDIO
    elif ext in ["mp4", "avi", "mov", "wmv", "webm"]:
        return FileType.VIDEO
    elif ext in ["pdf", "doc", "docx", "txt", "rtf"]:
        return FileType.DOCUMENT

    return FileType.OTHER


def add_storage_routes(app: FastAPI):
    """Add storage routes to FastAPI application."""

    @app.post("/api/storage/upload", response_model=FileMetadataResponse)
    async def upload_file(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        user_id: Optional[str] = Form(None),
        file_type: Optional[str] = Form(None),
        storage_class: str = Form("standard"),
        expires_hours: Optional[int] = Form(None),
        tags: str = Form("{}"),  # JSON string
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """Upload a file to storage."""
        try:
            # Parse tags
            import json

            file_tags = json.loads(tags) if tags != "{}" else {}

            # Read file content
            content = await file.read()

            if len(content) == 0:
                raise HTTPException(status_code=400, detail="Empty file")

            # Determine file type
            detected_file_type = (
                FileType(file_type)
                if file_type
                else determine_file_type(
                    file.filename or "unknown",
                    file.content_type or "application/octet-stream",
                )
            )

            # Create file metadata
            from .production_file_storage import FileMetadata
            import uuid

            file_metadata = FileMetadata(
                file_id=str(uuid.uuid4()),
                filename=file.filename or "unnamed",
                content_type=file.content_type or "application/octet-stream",
                file_size=len(content),
                file_type=detected_file_type,
                storage_class=StorageClass(storage_class),
                user_id=user_id,
                tags=file_tags,
            )

            # Set expiration if specified
            if expires_hours:
                from datetime import timedelta

                file_metadata.expires_at = datetime.now() + timedelta(
                    hours=expires_hours
                )

            # Upload file
            result = await storage_manager.upload_file(content, file_metadata)

            if not result.success:
                raise HTTPException(
                    status_code=500, detail=f"Upload failed: {result.error_message}"
                )

            # Log upload event
            background_tasks.add_task(
                EventPublisher.publish_audit_event,
                "audit.file.uploaded",
                {
                    "file_id": file_metadata.file_id,
                    "filename": file_metadata.filename,
                    "file_size": file_metadata.file_size,
                    "user_id": user_id,
                    "storage_provider": (
                        result.file_metadata.storage_provider.value
                        if result.file_metadata
                        else None
                    ),
                },
                user_id,
            )

            # Return metadata
            return FileMetadataResponse(
                file_id=result.file_metadata.file_id,
                filename=result.file_metadata.filename,
                content_type=result.file_metadata.content_type,
                file_size=result.file_metadata.file_size,
                file_type=result.file_metadata.file_type.value,
                storage_provider=result.file_metadata.storage_provider.value,
                storage_path=result.file_metadata.storage_path,
                cdn_url=result.cdn_url or None,
                created_at=result.file_metadata.created_at.isoformat(),
                expires_at=(
                    result.file_metadata.expires_at.isoformat()
                    if result.file_metadata.expires_at
                    else None
                ),
                tags=result.file_metadata.tags,
            )

        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid tags JSON")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

    @app.get("/api/storage/download/{file_path:path}")
    async def download_file(
        file_path: str,
        range: Optional[str] = None,
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """Download a file from storage."""
        try:
            # Get range header if provided
            range_header = range if range else None

            # Download file
            result = await storage_manager.download_file(
                file_path, range_header=range_header
            )

            if not result.success:
                raise HTTPException(
                    status_code=404, detail=f"File not found: {result.error_message}"
                )

            # Create streaming response
            def generate():
                yield result.content

            headers = {
                "Content-Length": str(result.file_size),
                "Content-Type": result.content_type,
                "Cache-Control": "public, max-age=3600",
            }

            # Add range headers if applicable
            if range_header:
                headers["Accept-Ranges"] = "bytes"
                headers["Content-Range"] = (
                    f"bytes 0-{result.file_size-1}/{result.file_size}"
                )

            return StreamingResponse(
                generate(), media_type=result.content_type, headers=headers
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

    @app.delete("/api/storage/delete/{file_path:path}")
    async def delete_file(
        file_path: str,
        background_tasks: BackgroundTasks,
        delete_from_all: bool = Query(False),
        user_id: Optional[str] = Query(None),
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """Delete a file from storage."""
        try:
            # Delete file
            success = await storage_manager.delete_file(
                file_path, delete_from_all=delete_from_all
            )

            if not success:
                raise HTTPException(
                    status_code=404, detail="File not found or delete failed"
                )

            # Log delete event
            background_tasks.add_task(
                EventPublisher.publish_audit_event,
                "audit.file.deleted",
                {
                    "file_path": file_path,
                    "delete_from_all": delete_from_all,
                    "user_id": user_id,
                },
                user_id,
            )

            return {"success": True, "message": "File deleted successfully"}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")

    @app.get(
        "/api/storage/metadata/{file_path:path}", response_model=FileMetadataResponse
    )
    async def get_file_metadata(
        file_path: str,
        provider: Optional[str] = Query(None),
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """Get file metadata."""
        try:
            # Parse provider if specified
            storage_provider = StorageProvider(provider) if provider else None

            # Get metadata
            metadata = await storage_manager.get_file_metadata(
                file_path, storage_provider
            )

            if not metadata:
                raise HTTPException(status_code=404, detail="File metadata not found")

            return FileMetadataResponse(
                file_id=metadata.file_id,
                filename=metadata.filename,
                content_type=metadata.content_type,
                file_size=metadata.file_size,
                file_type=metadata.file_type.value,
                storage_provider=metadata.storage_provider.value,
                storage_path=metadata.storage_path,
                cdn_url=metadata.cdn_url,
                created_at=metadata.created_at.isoformat(),
                expires_at=(
                    metadata.expires_at.isoformat() if metadata.expires_at else None
                ),
                tags=metadata.tags,
            )

        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid provider")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Metadata error: {str(e)}")

    @app.get("/api/storage/presigned-url/{file_path:path}")
    async def generate_presigned_url(
        file_path: str,
        expiration: int = Query(3600, ge=60, le=86400),
        method: str = Query("GET"),
        provider: Optional[str] = Query(None),
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """Generate presigned URL for file access."""
        try:
            # Parse provider if specified
            storage_provider = StorageProvider(provider) if provider else None

            # Generate URL
            url = await storage_manager.generate_presigned_url(
                file_path, expiration, method, storage_provider
            )

            if not url:
                raise HTTPException(
                    status_code=404, detail="Could not generate presigned URL"
                )

            return {
                "url": url,
                "expiration_seconds": expiration,
                "method": method,
                "generated_at": datetime.now().isoformat(),
            }

        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid provider or method")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"URL generation error: {str(e)}"
            )

    # 🔒 SECURED ADMIN ENDPOINTS - JWT + CERTIFICATE AUTH REQUIRED
    @app.get("/admin/storage/health")
    async def storage_health_check(
        session: AdminSession = Depends(require_admin_permission(AdminPermission.STORAGE_ADMIN, SecurityLevel.MEDIUM)),
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """🔒 SECURED: Get storage system health status - STORAGE_ADMIN required."""
        return await storage_manager.health_check()

    @app.get("/admin/storage/metrics")
    async def storage_metrics(
        session: AdminSession = Depends(require_admin_permission(AdminPermission.STORAGE_ADMIN, SecurityLevel.MEDIUM)),
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """🔒 SECURED: Get storage system metrics - STORAGE_ADMIN required."""
        return storage_manager.get_metrics()

    @app.get("/admin/storage/health-report")
    async def storage_health_report(
        session: AdminSession = Depends(require_admin_permission(AdminPermission.STORAGE_ADMIN, SecurityLevel.HIGH)),
        health_monitor: StorageHealthMonitor = Depends(get_health_monitor),
    ):
        """🔒 SECURED: Get comprehensive health report - STORAGE_ADMIN + HIGH security required."""
        return health_monitor.get_health_report()

    @app.post("/admin/storage/benchmark/{provider}")
    async def run_benchmark(
        provider: str,
        background_tasks: BackgroundTasks,
        session: AdminSession = Depends(require_admin_permission(AdminPermission.STORAGE_ADMIN, SecurityLevel.HIGH)),
        health_monitor: StorageHealthMonitor = Depends(get_health_monitor),
    ):
        """🔒 SECURED: Run performance benchmark - STORAGE_ADMIN + HIGH security required."""
        try:
            storage_provider = StorageProvider(provider)

            # Run benchmark in background
            background_tasks.add_task(health_monitor._run_benchmark, storage_provider)

            return {
                "message": f"Benchmark started for {provider}",
                "provider": provider,
                "started_at": datetime.now().isoformat(),
                "initiated_by": session.user_id
            }

        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid provider")

    @app.post("/admin/storage/force-health-check")
    async def force_health_check(
        background_tasks: BackgroundTasks,
        session: AdminSession = Depends(require_admin_permission(AdminPermission.STORAGE_ADMIN, SecurityLevel.HIGH)),
        health_monitor: StorageHealthMonitor = Depends(get_health_monitor),
    ):
        """🔒 SECURED: Force health check - STORAGE_ADMIN + HIGH security required."""
        try:
            # Run health checks in background
            for provider in health_monitor.storage_manager.providers.keys():
                background_tasks.add_task(
                    health_monitor._perform_health_check, provider
                )

            return {
                "message": "Health checks initiated for all providers",
                "providers": [
                    p.value for p in health_monitor.storage_manager.providers.keys()
                ],
                "initiated_at": datetime.now().isoformat(),
                "initiated_by": session.user_id
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Health check error: {str(e)}")

    # List files endpoint
    @app.get("/api/storage/list")
    async def list_files(
        prefix: str = Query(""),
        limit: int = Query(100, ge=1, le=1000),
        continuation_token: Optional[str] = Query(None),
        provider: Optional[str] = Query(None),
        storage_manager: ProductionFileStorage = Depends(get_storage_manager),
    ):
        """List files with pagination."""
        try:
            # Parse provider if specified
            storage_provider = StorageProvider(provider) if provider else None

            # Get provider instance
            if storage_provider:
                if storage_provider not in storage_manager.providers:
                    raise HTTPException(
                        status_code=400, detail="Provider not available"
                    )
                provider_instance = storage_manager.providers[storage_provider]
            else:
                # Use first available provider
                provider_instance = next(iter(storage_manager.providers.values()))

            # List files
            files, next_token = await provider_instance.list_files(
                prefix=prefix, limit=limit, continuation_token=continuation_token
            )

            # Convert to response format
            file_list = []
            for file_metadata in files:
                file_list.append(
                    {
                        "file_id": file_metadata.file_id,
                        "filename": file_metadata.filename,
                        "content_type": file_metadata.content_type,
                        "file_size": file_metadata.file_size,
                        "file_type": file_metadata.file_type.value,
                        "storage_path": file_metadata.storage_path,
                        "created_at": file_metadata.created_at.isoformat(),
                    }
                )

            return {
                "files": file_list,
                "count": len(file_list),
                "next_token": next_token,
                "has_more": next_token is not None,
            }

        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid provider")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"List error: {str(e)}")


def create_storage_app() -> FastAPI:
    """Create FastAPI application with storage integration."""
    app = FastAPI(
        title="AI Teddy Bear Storage API", version="1.0.0", lifespan=storage_lifespan
    )

    # Add storage routes
    add_storage_routes(app)

    return app


# Create the main application
storage_app = create_storage_app()
