"""Base storage adapter interface for Eleanor evidence storage.

Provides abstract base class for all storage backends (local, S3, Azure, GCS).
"""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, BinaryIO
from uuid import UUID


class StorageBackend(str, Enum):
    """Supported storage backends."""

    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"


@dataclass
class StorageConfig:
    """Configuration for storage adapter."""

    backend: str = "local"
    bucket: str | None = None
    region: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    endpoint_url: str | None = None  # For S3-compatible storage (MinIO, etc.)
    connection_string: str | None = None  # For Azure
    local_path: str = "/app/evidence"

    # Advanced options
    multipart_threshold: int = 100 * 1024 * 1024  # 100MB
    multipart_chunksize: int = 10 * 1024 * 1024   # 10MB
    max_concurrency: int = 10

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.backend in ("s3", "gcs") and not self.bucket:
            raise ValueError(f"{self.backend} backend requires a bucket name")
        if self.backend == "azure" and not self.bucket:
            raise ValueError("Azure backend requires a container name (bucket)")


@dataclass
class StorageFile:
    """Metadata for a stored file."""

    key: str  # Full path/key in storage
    size: int
    content_type: str | None = None
    etag: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    # Computed hashes (if available)
    sha256: str | None = None
    sha1: str | None = None
    md5: str | None = None


@dataclass
class StorageStats:
    """Storage usage statistics."""

    total_files: int
    total_size: int
    bucket: str | None = None
    prefix: str | None = None


@dataclass
class UploadResult:
    """Result of an upload operation."""

    key: str
    size: int
    sha256: str
    sha1: str
    md5: str
    etag: str | None = None
    content_type: str | None = None
    storage_url: str | None = None  # Full URL if applicable


class StorageAdapter(ABC):
    """Abstract base class for storage adapters.

    All storage adapters must implement these methods to provide
    a consistent interface for evidence storage operations.
    """

    name: str = "base"

    def __init__(self, config: StorageConfig):
        """Initialize adapter with configuration."""
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if adapter is connected."""
        return self._connected

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to storage backend.

        Returns:
            True if connection successful.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and clean up resources."""
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check storage backend health.

        Returns:
            Dictionary with status and any diagnostics.
        """
        ...

    # =========================================================================
    # Upload Operations
    # =========================================================================

    @abstractmethod
    async def upload_file(
        self,
        file: BinaryIO,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload a file to storage.

        Args:
            file: File-like object to upload.
            key: Destination key/path in storage.
            content_type: MIME type of the file.
            metadata: Additional metadata to store.

        Returns:
            UploadResult with file info and computed hashes.
        """
        ...

    @abstractmethod
    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload raw bytes to storage.

        Args:
            data: Bytes to upload.
            key: Destination key/path.
            content_type: MIME type.
            metadata: Additional metadata.

        Returns:
            UploadResult with file info and computed hashes.
        """
        ...

    async def upload_with_hashing(
        self,
        file: BinaryIO,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload file with hash computation during streaming.

        This default implementation reads the file, computes hashes,
        and then calls upload_bytes. Subclasses may override for
        more efficient streaming hash computation.
        """
        sha256 = hashlib.sha256()
        sha1 = hashlib.sha1()
        md5 = hashlib.md5()

        chunks = []
        while chunk := file.read(8192):
            chunks.append(chunk)
            sha256.update(chunk)
            sha1.update(chunk)
            md5.update(chunk)

        data = b"".join(chunks)

        result = await self.upload_bytes(data, key, content_type, metadata)
        result.sha256 = sha256.hexdigest()
        result.sha1 = sha1.hexdigest()
        result.md5 = md5.hexdigest()

        return result

    # =========================================================================
    # Download Operations
    # =========================================================================

    @abstractmethod
    async def download_file(
        self,
        key: str,
        destination: BinaryIO,
    ) -> StorageFile:
        """Download a file from storage.

        Args:
            key: Source key/path in storage.
            destination: File-like object to write to.

        Returns:
            StorageFile metadata.
        """
        ...

    @abstractmethod
    async def download_bytes(self, key: str) -> bytes:
        """Download file content as bytes.

        Args:
            key: Source key/path.

        Returns:
            File content as bytes.
        """
        ...

    @abstractmethod
    async def stream_download(
        self,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream download file content.

        Args:
            key: Source key/path.
            chunk_size: Size of chunks to yield.

        Yields:
            Chunks of file content.
        """
        ...

    @abstractmethod
    async def get_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: str | None = None,
    ) -> str:
        """Generate a presigned download URL.

        Args:
            key: Source key/path.
            expires_in: URL expiration time in seconds.
            filename: Suggested download filename.

        Returns:
            Presigned URL for downloading.
        """
        ...

    # =========================================================================
    # File Operations
    # =========================================================================

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a file exists in storage.

        Args:
            key: Key/path to check.

        Returns:
            True if file exists.
        """
        ...

    @abstractmethod
    async def get_metadata(self, key: str) -> StorageFile:
        """Get file metadata without downloading content.

        Args:
            key: Key/path of file.

        Returns:
            StorageFile with metadata.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a file from storage.

        Args:
            key: Key/path to delete.

        Returns:
            True if deletion successful.
        """
        ...

    @abstractmethod
    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple files.

        Args:
            keys: List of keys to delete.

        Returns:
            Dictionary mapping key to deletion success.
        """
        ...

    @abstractmethod
    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Copy a file within storage.

        Args:
            source_key: Source key/path.
            dest_key: Destination key/path.

        Returns:
            StorageFile for the copied file.
        """
        ...

    @abstractmethod
    async def move(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Move a file within storage.

        Args:
            source_key: Source key/path.
            dest_key: Destination key/path.

        Returns:
            StorageFile for the moved file.
        """
        ...

    # =========================================================================
    # Listing Operations
    # =========================================================================

    @abstractmethod
    async def list_files(
        self,
        prefix: str = "",
        limit: int | None = None,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageFile], str | None]:
        """List files with optional prefix filter.

        Args:
            prefix: Filter files by key prefix.
            limit: Maximum files to return.
            continuation_token: Token for pagination.

        Returns:
            Tuple of (files list, next continuation token or None).
        """
        ...

    @abstractmethod
    async def get_stats(self, prefix: str = "") -> StorageStats:
        """Get storage usage statistics.

        Args:
            prefix: Optional prefix to filter by.

        Returns:
            StorageStats with usage info.
        """
        ...

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def generate_key(
        self,
        case_id: UUID,
        filename: str,
        timestamp: datetime | None = None,
    ) -> str:
        """Generate a storage key for evidence.

        Args:
            case_id: Case UUID.
            filename: Original filename.
            timestamp: Optional timestamp (defaults to now).

        Returns:
            Generated storage key.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
        safe_filename = self._sanitize_filename(filename)

        return f"{case_id}/{ts_str}_{safe_filename}"

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for storage.

        Args:
            filename: Original filename.

        Returns:
            Sanitized filename safe for storage.
        """
        # Replace problematic characters
        safe = filename.replace("/", "_").replace("\\", "_")
        safe = safe.replace("\x00", "").replace("..", "_")

        # Limit length
        if len(safe) > 255:
            ext_start = safe.rfind(".")
            if ext_start > 0:
                ext = safe[ext_start:]
                safe = safe[:255 - len(ext)] + ext
            else:
                safe = safe[:255]

        return safe

    async def compute_hashes(self, key: str) -> dict[str, str]:
        """Compute hashes for a stored file.

        Args:
            key: Key/path of file.

        Returns:
            Dictionary with sha256, sha1, md5 hashes.
        """
        sha256 = hashlib.sha256()
        sha1 = hashlib.sha1()
        md5 = hashlib.md5()

        async for chunk in self.stream_download(key):
            sha256.update(chunk)
            sha1.update(chunk)
            md5.update(chunk)

        return {
            "sha256": sha256.hexdigest(),
            "sha1": sha1.hexdigest(),
            "md5": md5.hexdigest(),
        }
