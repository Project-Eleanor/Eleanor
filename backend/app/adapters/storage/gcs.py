"""Google Cloud Storage adapter for Eleanor evidence.

Provides storage operations using Google Cloud Storage.
"""

import hashlib
import logging
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, BinaryIO

from app.adapters.storage.base import (
    StorageAdapter,
    StorageConfig,
    StorageFile,
    StorageStats,
    UploadResult,
)

logger = logging.getLogger(__name__)


class GCSStorageAdapter(StorageAdapter):
    """Google Cloud Storage adapter.

    Uses google-cloud-storage SDK for all GCS operations.
    Supports service account and application default credentials.
    """

    name = "gcs"

    def __init__(self, config: StorageConfig):
        """Initialize GCS storage adapter.

        Args:
            config: Storage configuration with bucket and credentials.
        """
        super().__init__(config)
        self._client = None
        self._bucket = None

    async def connect(self) -> bool:
        """Initialize GCS client and verify bucket access."""
        try:
            from google.cloud import storage
            from google.cloud.exceptions import NotFound

            # Build client
            if self.config.access_key:
                # access_key contains path to service account JSON
                self._client = storage.Client.from_service_account_json(
                    self.config.access_key
                )
            else:
                # Use application default credentials
                self._client = storage.Client()

            # Get bucket
            try:
                self._bucket = self._client.get_bucket(self.config.bucket)
            except NotFound:
                logger.error("GCS bucket not found: %s", self.config.bucket)
                return False

            self._connected = True
            logger.info("GCS storage connected: %s", self.config.bucket)
            return True

        except ImportError:
            logger.error(
                "google-cloud-storage not installed. Run: pip install google-cloud-storage"
            )
            return False
        except Exception as e:
            logger.error("Failed to connect to GCS: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close GCS client."""
        if self._client:
            self._client.close()
        self._client = None
        self._bucket = None
        self._connected = False

    async def health_check(self) -> dict[str, Any]:
        """Check GCS storage health."""
        if not self._bucket:
            return {"status": "disconnected", "backend": "gcs"}

        try:
            self._bucket.reload()
            return {
                "status": "healthy",
                "backend": "gcs",
                "bucket": self.config.bucket,
                "location": self._bucket.location,
                "storage_class": self._bucket.storage_class,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "gcs",
                "error": str(e),
            }

    async def upload_file(
        self,
        file: BinaryIO,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload file with hash computation."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        # Read and hash content
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
        size = len(data)

        # Upload blob
        blob = self._bucket.blob(key)

        if content_type:
            blob.content_type = content_type

        if metadata:
            blob.metadata = metadata

        blob.upload_from_string(data, content_type=content_type)

        return UploadResult(
            key=key,
            size=size,
            sha256=sha256.hexdigest(),
            sha1=sha1.hexdigest(),
            md5=md5.hexdigest(),
            content_type=content_type,
            storage_url=f"gs://{self.config.bucket}/{key}",
        )

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload bytes to GCS."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        sha256 = hashlib.sha256(data).hexdigest()
        sha1 = hashlib.sha1(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()

        blob = self._bucket.blob(key)

        if metadata:
            blob.metadata = metadata

        blob.upload_from_string(data, content_type=content_type)

        return UploadResult(
            key=key,
            size=len(data),
            sha256=sha256,
            sha1=sha1,
            md5=md5,
            content_type=content_type,
            storage_url=f"gs://{self.config.bucket}/{key}",
        )

    async def download_file(
        self,
        key: str,
        destination: BinaryIO,
    ) -> StorageFile:
        """Download blob to destination."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)
        blob.download_to_file(destination)
        blob.reload()

        return StorageFile(
            key=key,
            size=blob.size,
            content_type=blob.content_type,
            etag=blob.etag,
            last_modified=blob.updated,
            metadata=blob.metadata or {},
        )

    async def download_bytes(self, key: str) -> bytes:
        """Download blob as bytes."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)
        return blob.download_as_bytes()

    async def stream_download(
        self,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream blob content."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)

        # GCS SDK doesn't have native async streaming,
        # so we download in chunks using range requests
        blob.reload()
        total_size = blob.size
        offset = 0

        while offset < total_size:
            end = min(offset + chunk_size - 1, total_size - 1)
            chunk = blob.download_as_bytes(start=offset, end=end)
            yield chunk
            offset = end + 1

    async def get_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: str | None = None,
    ) -> str:
        """Generate signed URL for download."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)

        kwargs: dict[str, Any] = {
            "expiration": timedelta(seconds=expires_in),
            "method": "GET",
        }

        if filename:
            kwargs["response_disposition"] = f'attachment; filename="{filename}"'

        return blob.generate_signed_url(**kwargs)

    async def exists(self, key: str) -> bool:
        """Check if blob exists."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)
        return blob.exists()

    async def get_metadata(self, key: str) -> StorageFile:
        """Get blob metadata."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)
        blob.reload()

        return StorageFile(
            key=key,
            size=blob.size,
            content_type=blob.content_type,
            etag=blob.etag,
            last_modified=blob.updated,
            metadata=blob.metadata or {},
        )

    async def delete(self, key: str) -> bool:
        """Delete a blob."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        try:
            blob = self._bucket.blob(key)
            blob.delete()
            return True
        except Exception as e:
            logger.error("Failed to delete %s: %s", key, e)
            return False

    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple blobs."""
        if not self._bucket or not keys:
            return {}

        results = {}

        # GCS supports batch delete
        with self._client.batch():
            for key in keys:
                try:
                    blob = self._bucket.blob(key)
                    blob.delete()
                    results[key] = True
                except Exception as e:
                    logger.error("Failed to delete %s: %s", key, e)
                    results[key] = False

        return results

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Copy a blob within bucket."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        source_blob = self._bucket.blob(source_key)
        dest_blob = self._bucket.copy_blob(source_blob, self._bucket, dest_key)

        return StorageFile(
            key=dest_key,
            size=dest_blob.size,
            content_type=dest_blob.content_type,
            etag=dest_blob.etag,
            last_modified=dest_blob.updated,
            metadata=dest_blob.metadata or {},
        )

    async def move(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Move a blob (copy + delete)."""
        result = await self.copy(source_key, dest_key)
        await self.delete(source_key)
        return result

    async def list_files(
        self,
        prefix: str = "",
        limit: int | None = None,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageFile], str | None]:
        """List blobs with prefix."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        kwargs: dict[str, Any] = {}
        if prefix:
            kwargs["prefix"] = prefix
        if limit:
            kwargs["max_results"] = limit
        if continuation_token:
            kwargs["page_token"] = continuation_token

        blobs = self._bucket.list_blobs(**kwargs)
        page = next(blobs.pages)

        files = [
            StorageFile(
                key=blob.name,
                size=blob.size,
                content_type=blob.content_type,
                etag=blob.etag,
                last_modified=blob.updated,
                metadata=blob.metadata or {},
            )
            for blob in page
        ]

        next_token = blobs.next_page_token
        return files, next_token

    async def get_stats(self, prefix: str = "") -> StorageStats:
        """Get storage statistics."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        total_files = 0
        total_size = 0

        kwargs: dict[str, Any] = {}
        if prefix:
            kwargs["prefix"] = prefix

        for blob in self._bucket.list_blobs(**kwargs):
            total_files += 1
            total_size += blob.size or 0

        return StorageStats(
            total_files=total_files,
            total_size=total_size,
            bucket=self.config.bucket,
            prefix=prefix or None,
        )

    async def get_upload_url(
        self,
        key: str,
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> str:
        """Generate signed URL for direct upload."""
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)

        kwargs: dict[str, Any] = {
            "expiration": timedelta(seconds=expires_in),
            "method": "PUT",
        }

        if content_type:
            kwargs["content_type"] = content_type

        return blob.generate_signed_url(**kwargs)

    async def make_public(self, key: str) -> str:
        """Make a blob publicly accessible and return public URL.

        Use with caution - makes blob accessible to anyone.
        """
        if not self._bucket:
            raise RuntimeError("GCS client not connected")

        blob = self._bucket.blob(key)
        blob.make_public()
        return blob.public_url
