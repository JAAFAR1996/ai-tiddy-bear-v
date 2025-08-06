"""
Advanced Compression and Encoding Optimization System
Supports gzip, brotli, image optimization, and audio compression with child-safe content handling
"""

import gzip
import brotli
import logging
import hashlib
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from pydub import AudioSegment

# Import shared audio format for base compatibility

from src.core.exceptions import ValidationError
from src.utils.file_utils import ensure_directory_exists, get_file_size


logger = logging.getLogger(__name__)


class CompressionType(Enum):
    """Supported compression types."""

    GZIP = "gzip"
    BROTLI = "brotli"
    DEFLATE = "deflate"


class ImageFormat(Enum):
    """Supported optimized image formats."""

    WEBP = "webp"
    AVIF = "avif"
    JPEG = "jpeg"
    PNG = "png"


# SPECIALIZED FOR COMPRESSION ONLY - inherits from BaseAudioFormat for consistency
class CompressionAudioFormat(Enum):
    """
    Specialized audio formats for compression/optimization ONLY.
    ============================================================

    IMPORTANT: This is a specialized enum for compression-specific formats.
    Inherits from BaseAudioFormat for consistency and validation.
    Do NOT use this outside of compression/performance optimization context.

    For general audio operations, use src.shared.audio_types.AudioFormat
    """

    MP3 = "mp3"
    OGG = "ogg"
    AAC = "aac"
    WEBM = "webm"  # Specialized for web compression


@dataclass
class CompressionConfig:
    """Compression configuration."""

    enabled: bool = True
    gzip_enabled: bool = True
    brotli_enabled: bool = True
    gzip_level: int = 6  # 1-9, higher = better compression but slower
    brotli_level: int = 6  # 0-11, higher = better compression but slower
    min_size_bytes: int = 1024  # Don't compress files smaller than this
    max_size_bytes: int = 50 * 1024 * 1024  # Don't compress files larger than 50MB
    mime_types: List[str] = field(
        default_factory=lambda: [
            "text/html",
            "text/css",
            "text/javascript",
            "application/javascript",
            "application/json",
            "text/xml",
            "application/xml",
            "text/plain",
            "image/svg+xml",
        ]
    )
    exclude_extensions: List[str] = field(
        default_factory=lambda: [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".mp3",
            ".mp4",
            ".avi",
            ".mov",
        ]
    )


@dataclass
class ImageOptimizationConfig:
    """Image optimization configuration."""

    enabled: bool = True
    webp_quality: int = 85
    jpeg_quality: int = 85
    png_optimize: bool = True
    progressive_jpeg: bool = True
    max_width: int = 1920
    max_height: int = 1080
    child_safe_watermark: bool = True  # Add child-safe watermark
    preserve_metadata: bool = False  # Remove metadata for privacy


@dataclass
class AudioOptimizationConfig:
    """Audio optimization configuration."""

    enabled: bool = True
    mp3_bitrate: str = "128k"
    ogg_quality: int = 5  # 0-10 scale
    normalize_audio: bool = True
    remove_silence: bool = True
    max_duration_seconds: int = 300  # 5 minutes max for child safety
    child_content_filter: bool = True


@dataclass
class CompressionResult:
    """Result of compression operation."""

    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_type: CompressionType
    processing_time_ms: float
    cached: bool = False
    child_safe: bool = True


class BaseCompressor(ABC):
    """Base class for compression implementations."""

    @abstractmethod
    async def compress(self, data: bytes) -> bytes:
        """Compress data."""
        pass

    @abstractmethod
    async def decompress(self, data: bytes) -> bytes:
        """Decompress data."""
        pass

    @abstractmethod
    def get_compression_type(self) -> CompressionType:
        """Get compression type."""
        pass


class GzipCompressor(BaseCompressor):
    """Gzip compression implementation."""

    def __init__(self, level: int = 6):
        self.level = level

    async def compress(self, data: bytes) -> bytes:
        """Compress data using gzip."""
        return gzip.compress(data, compresslevel=self.level)

    async def decompress(self, data: bytes) -> bytes:
        """Decompress gzip data."""
        return gzip.decompress(data)

    def get_compression_type(self) -> CompressionType:
        return CompressionType.GZIP


class BrotliCompressor(BaseCompressor):
    """Brotli compression implementation."""

    def __init__(self, level: int = 6):
        self.level = level

    async def compress(self, data: bytes) -> bytes:
        """Compress data using Brotli."""
        return brotli.compress(data, quality=self.level)

    async def decompress(self, data: bytes) -> bytes:
        """Decompress Brotli data."""
        return brotli.decompress(data)

    def get_compression_type(self) -> CompressionType:
        return CompressionType.BROTLI


class ImageOptimizer:
    """Advanced image optimization with child-safe features."""

    def __init__(self, config: ImageOptimizationConfig):
        self.config = config

    async def optimize_image(
        self, input_path: str, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Optimize image with multiple format options."""
        if not os.path.exists(input_path):
            raise ValidationError(f"Image file not found: {input_path}")

        input_path = Path(input_path)
        if not output_path:
            output_path = input_path.with_suffix(".webp")
        else:
            output_path = Path(output_path)

        original_size = get_file_size(str(input_path))

        try:
            # Open and validate image
            with Image.open(input_path) as img:
                # Validate image is child-appropriate (basic check)
                await self._validate_child_safe_image(img)

                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Resize if too large
                if (
                    img.size[0] > self.config.max_width
                    or img.size[1] > self.config.max_height
                ):
                    img.thumbnail(
                        (self.config.max_width, self.config.max_height),
                        Image.Resampling.LANCZOS,
                    )

                # Remove metadata for privacy
                if not self.config.preserve_metadata:
                    data = list(img.getdata())
                    img_without_exif = Image.new(img.mode, img.size)
                    img_without_exif.putdata(data)
                    img = img_without_exif

                # Add child-safe watermark if enabled
                if self.config.child_safe_watermark:
                    img = await self._add_child_safe_watermark(img)

                # Save in optimized format
                await self._save_optimized_image(img, output_path)

        except Exception as e:
            logger.error(f"Image optimization failed for {input_path}: {e}")
            raise ValidationError(f"Image optimization failed: {e}")

        optimized_size = get_file_size(str(output_path))
        compression_ratio = (
            (original_size - optimized_size) / original_size if original_size > 0 else 0
        )

        return {
            "original_path": str(input_path),
            "optimized_path": str(output_path),
            "original_size": original_size,
            "optimized_size": optimized_size,
            "compression_ratio": compression_ratio,
            "child_safe": True,
        }

    async def _validate_child_safe_image(self, img: Image.Image) -> None:
        """Basic validation for child-appropriate content."""
        # This is a placeholder for more sophisticated content validation
        # In production, you would integrate with content moderation APIs

        # Basic checks
        if img.size[0] < 10 or img.size[1] < 10:
            raise ValidationError("Image too small")

        if img.size[0] > 4000 or img.size[1] > 4000:
            raise ValidationError("Image too large")

    async def _add_child_safe_watermark(self, img: Image.Image) -> Image.Image:
        """Add subtle child-safe watermark."""
        # This would add a subtle watermark indicating child-safe content
        # For now, just return the original image
        return img

    async def _save_optimized_image(self, img: Image.Image, output_path: Path) -> None:
        """Save image in optimized format."""
        format_map = {".webp": "WEBP", ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}

        output_format = format_map.get(output_path.suffix.lower(), "WEBP")

        save_kwargs = {}
        if output_format == "WEBP":
            save_kwargs = {"quality": self.config.webp_quality, "optimize": True}
        elif output_format == "JPEG":
            save_kwargs = {
                "quality": self.config.jpeg_quality,
                "optimize": True,
                "progressive": self.config.progressive_jpeg,
            }
        elif output_format == "PNG":
            save_kwargs = {"optimize": self.config.png_optimize}

        img.save(output_path, format=output_format, **save_kwargs)

    async def batch_optimize(
        self, input_dir: str, output_dir: str
    ) -> List[Dict[str, Any]]:
        """Optimize all images in a directory."""
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if not input_path.exists():
            raise ValidationError(f"Input directory not found: {input_dir}")

        ensure_directory_exists(str(output_path))

        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}
        image_files = [
            f
            for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]

        results = []
        for image_file in image_files:
            try:
                output_file = output_path / f"{image_file.stem}.webp"
                result = await self.optimize_image(str(image_file), str(output_file))
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to optimize {image_file}: {e}")
                results.append(
                    {
                        "original_path": str(image_file),
                        "error": str(e),
                        "child_safe": False,
                    }
                )

        return results


class AudioOptimizer:
    """Audio optimization for TTS responses with child-safe features."""

    def __init__(self, config: AudioOptimizationConfig):
        self.config = config

    async def optimize_audio(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        target_format: str = "mp3",
    ) -> Dict[str, Any]:
        """Optimize audio file for child-safe TTS responses."""
        if not os.path.exists(input_path):
            raise ValidationError(f"Audio file not found: {input_path}")

        input_path = Path(input_path)
        if not output_path:
            output_path = input_path.with_suffix(f".{target_format.value}")
        else:
            output_path = Path(output_path)

        original_size = get_file_size(str(input_path))

        try:
            # Load audio
            audio = AudioSegment.from_file(str(input_path))

            # Child safety validation
            await self._validate_child_safe_audio(audio)

            # Apply optimizations
            if self.config.normalize_audio:
                audio = audio.normalize()

            if self.config.remove_silence:
                audio = self._remove_silence(audio)

            # Limit duration for child safety
            if len(audio) > self.config.max_duration_seconds * 1000:
                audio = audio[: self.config.max_duration_seconds * 1000]
                logger.warning(
                    f"Audio truncated to {self.config.max_duration_seconds} seconds for child safety"
                )

            # Export in optimized format
            export_kwargs = self._get_export_settings(target_format)
            audio.export(str(output_path), format=target_format.value, **export_kwargs)

        except Exception as e:
            logger.error(f"Audio optimization failed for {input_path}: {e}")
            raise ValidationError(f"Audio optimization failed: {e}")

        optimized_size = get_file_size(str(output_path))
        compression_ratio = (
            (original_size - optimized_size) / original_size if original_size > 0 else 0
        )

        return {
            "original_path": str(input_path),
            "optimized_path": str(output_path),
            "original_size": original_size,
            "optimized_size": optimized_size,
            "compression_ratio": compression_ratio,
            "duration_ms": len(audio),
            "child_safe": True,
            "format": target_format.value,
        }

    async def _validate_child_safe_audio(self, audio: AudioSegment) -> None:
        """Validate audio content is appropriate for children."""
        # Basic validation
        if len(audio) < 100:  # Less than 100ms
            raise ValidationError("Audio too short")

        if len(audio) > self.config.max_duration_seconds * 1000:
            logger.warning(f"Audio duration exceeds maximum: {len(audio)}ms")

        # Check for inappropriate volume levels
        if audio.max_dBFS > -3:
            logger.warning("Audio may be too loud for children")

    def _remove_silence(
        self, audio: AudioSegment, silence_thresh: int = -50
    ) -> AudioSegment:
        """Remove silence from audio."""
        # Simple silence removal - in production you might use more sophisticated algorithms
        return audio.strip_silence(silence_thresh=silence_thresh, padding=100)

    def _get_export_settings(self, format: CompressionAudioFormat) -> Dict[str, Any]:
        """Get export settings for different audio formats."""
        settings = {
            CompressionAudioFormat.MP3: {
                "bitrate": self.config.mp3_bitrate,
                "parameters": ["-q:a", "2"],  # High quality
            },
            CompressionAudioFormat.OGG: {
                "codec": "libvorbis",
                "parameters": ["-q:a", str(self.config.ogg_quality)],
            },
            CompressionAudioFormat.AAC: {"codec": "aac", "bitrate": "128k"},
            CompressionAudioFormat.WEBM: {"codec": "libopus", "bitrate": "128k"},
        }

        return settings.get(format, {})


class CompressionManager:
    """Main compression management system."""

    def __init__(
        self,
        compression_config: CompressionConfig,
        image_config: ImageOptimizationConfig,
        audio_config: AudioOptimizationConfig,
    ):
        self.compression_config = compression_config
        self.image_config = image_config
        self.audio_config = audio_config

        # Initialize compressors
        self.compressors = {}
        if compression_config.gzip_enabled:
            self.compressors[CompressionType.GZIP] = GzipCompressor(
                compression_config.gzip_level
            )
        if compression_config.brotli_enabled:
            self.compressors[CompressionType.BROTLI] = BrotliCompressor(
                compression_config.brotli_level
            )

        # Initialize optimizers
        self.image_optimizer = ImageOptimizer(image_config)
        self.audio_optimizer = AudioOptimizer(audio_config)

        # Compression cache
        self._compression_cache = {}

    async def compress_response(
        self, data: bytes, content_type: str, preferred_encoding: Optional[str] = None
    ) -> Tuple[bytes, CompressionType, CompressionResult]:
        """Compress HTTP response data."""
        if not self._should_compress(data, content_type):
            return (
                data,
                None,
                CompressionResult(
                    original_size=len(data),
                    compressed_size=len(data),
                    compression_ratio=0.0,
                    compression_type=None,
                    processing_time_ms=0.0,
                ),
            )

        # Check cache first
        data_hash = hashlib.md5(data).hexdigest()
        cache_key = f"{data_hash}_{preferred_encoding or 'auto'}"

        if cache_key in self._compression_cache:
            cached_result = self._compression_cache[cache_key]
            cached_result.cached = True
            return cached_result["data"], cached_result["type"], cached_result["result"]

        # Choose best compressor
        compressor_type = self._choose_compressor(preferred_encoding)
        if not compressor_type:
            return (
                data,
                None,
                CompressionResult(
                    original_size=len(data),
                    compressed_size=len(data),
                    compression_ratio=0.0,
                    compression_type=None,
                    processing_time_ms=0.0,
                ),
            )

        compressor = self.compressors[compressor_type]

        # Compress data
        import time

        start_time = time.time()

        try:
            compressed_data = await compressor.compress(data)
            processing_time = (time.time() - start_time) * 1000

            compression_ratio = (
                (len(data) - len(compressed_data)) / len(data) if len(data) > 0 else 0
            )

            result = CompressionResult(
                original_size=len(data),
                compressed_size=len(compressed_data),
                compression_ratio=compression_ratio,
                compression_type=compressor_type,
                processing_time_ms=processing_time,
            )

            # Cache result
            self._compression_cache[cache_key] = {
                "data": compressed_data,
                "type": compressor_type,
                "result": result,
            }

            # Limit cache size
            if len(self._compression_cache) > 1000:
                # Remove oldest entries
                keys_to_remove = list(self._compression_cache.keys())[:100]
                for key in keys_to_remove:
                    del self._compression_cache[key]

            return compressed_data, compressor_type, result

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return (
                data,
                None,
                CompressionResult(
                    original_size=len(data),
                    compressed_size=len(data),
                    compression_ratio=0.0,
                    compression_type=None,
                    processing_time_ms=processing_time,
                ),
            )

    def _should_compress(self, data: bytes, content_type: str) -> bool:
        """Determine if data should be compressed."""
        if not self.compression_config.enabled:
            return False

        # Check size limits
        data_size = len(data)
        if data_size < self.compression_config.min_size_bytes:
            return False
        if data_size > self.compression_config.max_size_bytes:
            return False

        # Check content type
        if content_type not in self.compression_config.mime_types:
            return False

        return True

    def _choose_compressor(
        self, preferred_encoding: Optional[str]
    ) -> Optional[CompressionType]:
        """Choose the best compressor based on preference and availability."""
        if preferred_encoding:
            if (
                preferred_encoding == "br"
                and CompressionType.BROTLI in self.compressors
            ):
                return CompressionType.BROTLI
            elif (
                preferred_encoding == "gzip"
                and CompressionType.GZIP in self.compressors
            ):
                return CompressionType.GZIP

        # Default preference: Brotli > Gzip
        if CompressionType.BROTLI in self.compressors:
            return CompressionType.BROTLI
        elif CompressionType.GZIP in self.compressors:
            return CompressionType.GZIP

        return None

    async def optimize_static_assets(
        self, assets_dir: str, output_dir: str
    ) -> Dict[str, Any]:
        """Optimize all static assets in a directory."""
        assets_path = Path(assets_dir)
        output_path = Path(output_dir)

        if not assets_path.exists():
            raise ValidationError(f"Assets directory not found: {assets_dir}")

        ensure_directory_exists(str(output_path))

        results = {
            "images": [],
            "audio": [],
            "total_original_size": 0,
            "total_optimized_size": 0,
            "overall_compression_ratio": 0.0,
        }

        # Process images
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}
        for file in assets_path.rglob("*"):
            if file.is_file() and file.suffix.lower() in image_extensions:
                try:
                    relative_path = file.relative_to(assets_path)
                    output_file = output_path / relative_path.with_suffix(".webp")
                    ensure_directory_exists(str(output_file.parent))

                    result = await self.image_optimizer.optimize_image(
                        str(file), str(output_file)
                    )
                    results["images"].append(result)
                    results["total_original_size"] += result["original_size"]
                    results["total_optimized_size"] += result["optimized_size"]
                except Exception as e:
                    logger.error(f"Failed to optimize image {file}: {e}")

        # Process audio files
        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}
        for file in assets_path.rglob("*"):
            if file.is_file() and file.suffix.lower() in audio_extensions:
                try:
                    relative_path = file.relative_to(assets_path)
                    output_file = output_path / relative_path.with_suffix(".mp3")
                    ensure_directory_exists(str(output_file.parent))

                    result = await self.audio_optimizer.optimize_audio(
                        str(file), str(output_file)
                    )
                    results["audio"].append(result)
                    results["total_original_size"] += result["original_size"]
                    results["total_optimized_size"] += result["optimized_size"]
                except Exception as e:
                    logger.error(f"Failed to optimize audio {file}: {e}")

        # Calculate overall compression ratio
        if results["total_original_size"] > 0:
            results["overall_compression_ratio"] = (
                results["total_original_size"] - results["total_optimized_size"]
            ) / results["total_original_size"]

        return results

    async def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression performance statistics."""
        cache_stats = {
            "cache_size": len(self._compression_cache),
            "cache_hit_ratio": 0.0,  # Would need to track hits/misses
        }

        compressor_stats = {}
        for comp_type in self.compressors:
            # In production, you'd track more detailed stats per compressor
            compressor_stats[comp_type.value] = {
                "enabled": True,
                "total_compressions": 0,
                "avg_compression_ratio": 0.0,
                "avg_processing_time_ms": 0.0,
            }

        return {
            "cache": cache_stats,
            "compressors": compressor_stats,
            "image_optimization": {
                "enabled": self.image_config.enabled,
                "webp_quality": self.image_config.webp_quality,
                "child_safe_watermark": self.image_config.child_safe_watermark,
            },
            "audio_optimization": {
                "enabled": self.audio_config.enabled,
                "max_duration_seconds": self.audio_config.max_duration_seconds,
                "child_content_filter": self.audio_config.child_content_filter,
            },
        }


# Factory function for easy initialization
def create_compression_manager(
    gzip_level: int = 6,
    brotli_level: int = 6,
    webp_quality: int = 85,
    mp3_bitrate: str = "128k",
) -> CompressionManager:
    """Create compression manager with default child-safe settings."""

    compression_config = CompressionConfig(
        gzip_level=gzip_level, brotli_level=brotli_level
    )

    image_config = ImageOptimizationConfig(
        webp_quality=webp_quality,
        child_safe_watermark=True,
        preserve_metadata=False,  # Remove metadata for privacy
    )

    audio_config = AudioOptimizationConfig(
        mp3_bitrate=mp3_bitrate,
        max_duration_seconds=300,  # 5 minutes max
        child_content_filter=True,
    )

    return CompressionManager(compression_config, image_config, audio_config)
