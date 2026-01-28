"""Local filesystem storage adapter for Eleanor evidence.

Provides storage operations using the local filesystem.
Suitable for development, single-node deployments, and air-gapped environments.
"""

import hashlib
import logging
import os
import shutil
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, BinaryIO

import aiofiles
import aiofiles.os

from app.adapters.storage.base import (
    StorageAdapter,
    StorageConfig,
    StorageFile,
    StorageStats,
    UploadResult,
)

logger = logging.getLogger(__name__)


class LocalStorageAdapter(StorageAdapter):
    """Local filesystem storage adapter.

    Stores files in a configurable local directory structure.
    Supports all standard storage operations with async file I/O.
    """

    name = "local"

    def __init__(self, config: StorageConfig):
        """Initialize local storage adapter.

        Args:
            config: Storage configuration with local_path set.
        """
        super().__init__(config)
        self.base_path = config.local_path

    async def connect(self) -> bool:
        """Ensure base directory exists and is writable."""
        try:
            os.makedirs(self.base_path, exist_ok=True)

            # Test write access
            test_file = os.path.join(self.base_path, ".write_test")
            async with aiofiles.open(test_file, "w") as f:
                await f.write("test")
            await aiofiles.os.remove(test_file)

            self._connected = True
            logger.info("Local storage connected: %s", self.base_path)
            return True
        except Exception as e:
            logger.error("Failed to connect local storage: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """No cleanup needed for local storage."""
        self._connected = False

    async def health_check(self) -> dict[str, Any]:
        """Check local storage health."""
        try:
            stat = os.statvfs(self.base_path)
            free_bytes = stat.f_bavail * stat.f_frsize
            total_bytes = stat.f_blocks * stat.f_frsize
            used_bytes = total_bytes - free_bytes

            return {
                "status": "healthy",
                "backend": "local",
                "path": self.base_path,
                "free_bytes": free_bytes,
                "used_bytes": used_bytes,
                "total_bytes": total_bytes,
                "free_percent": round(free_bytes / total_bytes * 100, 2) if total_bytes else 0,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "local",
                "error": str(e),
            }

    def _full_path(self, key: str) -> str:
        """Get full filesystem path for a key."""
        # Prevent directory traversal
        safe_key = os.path.normpath(key).lstrip(os.sep)
        return os.path.join(self.base_path, safe_key)

    async def upload_file(
        self,
        file: BinaryIO,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload file with hash computation."""
        full_path = self._full_path(key)
        dir_path = os.path.dirname(full_path)

        # Ensure directory exists
        os.makedirs(dir_path, exist_ok=True)

        # Compute hashes while writing
        sha256 = hashlib.sha256()
        sha1 = hashlib.sha1()
        md5 = hashlib.md5()
        size = 0

        async with aiofiles.open(full_path, "wb") as out_file:
            while chunk := file.read(8192):
                await out_file.write(chunk)
                sha256.update(chunk)
                sha1.update(chunk)
                md5.update(chunk)
                size += len(chunk)

        return UploadResult(
            key=key,
            size=size,
            sha256=sha256.hexdigest(),
            sha1=sha1.hexdigest(),
            md5=md5.hexdigest(),
            content_type=content_type,
            storage_url=f"file://{full_path}",
        )

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload bytes with hash computation."""
        full_path = self._full_path(key)
        dir_path = os.path.dirname(full_path)

        os.makedirs(dir_path, exist_ok=True)

        async with aiofiles.open(full_path, "wb") as f:
            await f.write(data)

        sha256 = hashlib.sha256(data).hexdigest()
        sha1 = hashlib.sha1(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()

        return UploadResult(
            key=key,
            size=len(data),
            sha256=sha256,
            sha1=sha1,
            md5=md5,
            content_type=content_type,
            storage_url=f"file://{full_path}",
        )

    async def download_file(
        self,
        key: str,
        destination: BinaryIO,
    ) -> StorageFile:
        """Download file to destination."""
        full_path = self._full_path(key)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {key}")

        async with aiofiles.open(full_path, "rb") as f:
            while chunk := await f.read(8192):
                destination.write(chunk)

        stat = os.stat(full_path)
        return StorageFile(
            key=key,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def download_bytes(self, key: str) -> bytes:
        """Download file content as bytes."""
        full_path = self._full_path(key)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {key}")

        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def stream_download(
        self,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream file content in chunks."""
        full_path = self._full_path(key)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {key}")

        async with aiofiles.open(full_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                yield chunk

    async def get_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: str | None = None,
    ) -> str:
        """Get file URL (returns file:// path for local storage)."""
        full_path = self._full_path(key)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {key}")
        return f"file://{full_path}"

    async def exists(self, key: str) -> bool:
        """Check if file exists."""
        full_path = self._full_path(key)
        return os.path.exists(full_path)

    async def get_metadata(self, key: str) -> StorageFile:
        """Get file metadata."""
        full_path = self._full_path(key)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {key}")

        stat = os.stat(full_path)
        return StorageFile(
            key=key,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def delete(self, key: str) -> bool:
        """Delete a file."""
        full_path = self._full_path(key)

        if not os.path.exists(full_path):
            return False

        try:
            await aiofiles.os.remove(full_path)

            # Clean up empty parent directories
            dir_path = os.path.dirname(full_path)
            while dir_path != self.base_path:
                if os.path.isdir(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    dir_path = os.path.dirname(dir_path)
                else:
                    break

            return True
        except Exception as e:
            logger.error("Failed to delete %s: %s", key, e)
            return False

    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple files."""
        results = {}
        for key in keys:
            results[key] = await self.delete(key)
        return results

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Copy a file."""
        source_path = self._full_path(source_key)
        dest_path = self._full_path(dest_key)

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_key}")

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(source_path, dest_path)

        stat = os.stat(dest_path)
        return StorageFile(
            key=dest_key,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def move(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Move a file."""
        source_path = self._full_path(source_key)
        dest_path = self._full_path(dest_key)

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_key}")

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.move(source_path, dest_path)

        # Clean up empty source directories
        source_dir = os.path.dirname(source_path)
        while source_dir != self.base_path:
            if os.path.isdir(source_dir) and not os.listdir(source_dir):
                os.rmdir(source_dir)
                source_dir = os.path.dirname(source_dir)
            else:
                break

        stat = os.stat(dest_path)
        return StorageFile(
            key=dest_key,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def list_files(
        self,
        prefix: str = "",
        limit: int | None = None,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageFile], str | None]:
        """List files with optional prefix filter."""
        base = self._full_path(prefix) if prefix else self.base_path
        files: list[StorageFile] = []
        count = 0

        # Handle continuation token (file path to start from)
        skip_until = continuation_token

        for root, _, filenames in os.walk(base):
            for filename in sorted(filenames):
                full_path = os.path.join(root, filename)
                key = os.path.relpath(full_path, self.base_path)

                # Skip files until we reach continuation point
                if skip_until and key <= skip_until:
                    continue
                skip_until = None

                stat = os.stat(full_path)
                files.append(
                    StorageFile(
                        key=key,
                        size=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                    )
                )

                count += 1
                if limit and count >= limit:
                    # Return last key as continuation token
                    return files, key

        return files, None

    async def get_stats(self, prefix: str = "") -> StorageStats:
        """Get storage statistics."""
        base = self._full_path(prefix) if prefix else self.base_path
        total_files = 0
        total_size = 0

        for root, _, filenames in os.walk(base):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                try:
                    stat = os.stat(full_path)
                    total_files += 1
                    total_size += stat.st_size
                except OSError:
                    continue

        return StorageStats(
            total_files=total_files,
            total_size=total_size,
            prefix=prefix or None,
        )

    def get_file_path(self, key: str) -> str:
        """Get the full filesystem path for a key.

        This is specific to local storage for use with FileResponse.
        """
        return self._full_path(key)
