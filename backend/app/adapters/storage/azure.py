"""Azure Blob Storage adapter for Eleanor evidence.

Provides storage operations using Microsoft Azure Blob Storage.
"""

import hashlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO

from app.adapters.storage.base import (
    StorageAdapter,
    StorageConfig,
    StorageFile,
    StorageStats,
    UploadResult,
)

logger = logging.getLogger(__name__)


class AzureBlobStorageAdapter(StorageAdapter):
    """Azure Blob Storage adapter.

    Uses azure-storage-blob SDK for all blob operations.
    Supports both connection string and account key authentication.
    """

    name = "azure"

    def __init__(self, config: StorageConfig):
        """Initialize Azure Blob storage adapter.

        Args:
            config: Storage configuration with container and credentials.
        """
        super().__init__(config)
        self._client = None
        self._container_client = None

    async def connect(self) -> bool:
        """Initialize Azure client and verify container access."""
        try:
            from azure.core.exceptions import ResourceNotFoundError
            from azure.storage.blob import BlobServiceClient

            # Build client using connection string or account key
            if self.config.connection_string:
                self._client = BlobServiceClient.from_connection_string(
                    self.config.connection_string
                )
            elif self.config.access_key and self.config.endpoint_url:
                # endpoint_url should be the account URL
                self._client = BlobServiceClient(
                    account_url=self.config.endpoint_url,
                    credential=self.config.access_key,
                )
            else:
                # Try DefaultAzureCredential for managed identity
                from azure.identity import DefaultAzureCredential

                credential = DefaultAzureCredential()
                if not self.config.endpoint_url:
                    raise ValueError(
                        "Azure endpoint_url required when using DefaultAzureCredential"
                    )
                self._client = BlobServiceClient(
                    account_url=self.config.endpoint_url,
                    credential=credential,
                )

            # Get container client
            self._container_client = self._client.get_container_client(self.config.bucket)

            # Verify container exists
            try:
                self._container_client.get_container_properties()
            except ResourceNotFoundError:
                logger.error("Azure container not found: %s", self.config.bucket)
                return False

            self._connected = True
            logger.info("Azure Blob storage connected: %s", self.config.bucket)
            return True

        except ImportError:
            logger.error(
                "azure-storage-blob not installed. Run: pip install azure-storage-blob azure-identity"
            )
            return False
        except Exception as e:
            logger.error("Failed to connect to Azure Blob: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close Azure client."""
        if self._client:
            self._client.close()
        self._client = None
        self._container_client = None
        self._connected = False

    async def health_check(self) -> dict[str, Any]:
        """Check Azure storage health."""
        if not self._container_client:
            return {"status": "disconnected", "backend": "azure"}

        try:
            props = self._container_client.get_container_properties()
            return {
                "status": "healthy",
                "backend": "azure",
                "container": self.config.bucket,
                "last_modified": props.get("last_modified"),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "azure",
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
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        from azure.storage.blob import ContentSettings

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
        blob_client = self._container_client.get_blob_client(key)

        content_settings = None
        if content_type:
            content_settings = ContentSettings(content_type=content_type)

        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=content_settings,
            metadata=metadata,
        )

        return UploadResult(
            key=key,
            size=size,
            sha256=sha256.hexdigest(),
            sha1=sha1.hexdigest(),
            md5=md5.hexdigest(),
            content_type=content_type,
            storage_url=blob_client.url,
        )

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload bytes to Azure."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        from azure.storage.blob import ContentSettings

        sha256 = hashlib.sha256(data).hexdigest()
        sha1 = hashlib.sha1(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()

        blob_client = self._container_client.get_blob_client(key)

        content_settings = None
        if content_type:
            content_settings = ContentSettings(content_type=content_type)

        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=content_settings,
            metadata=metadata,
        )

        return UploadResult(
            key=key,
            size=len(data),
            sha256=sha256,
            sha1=sha1,
            md5=md5,
            content_type=content_type,
            storage_url=blob_client.url,
        )

    async def download_file(
        self,
        key: str,
        destination: BinaryIO,
    ) -> StorageFile:
        """Download blob to destination."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        blob_client = self._container_client.get_blob_client(key)
        download_stream = blob_client.download_blob()

        for chunk in download_stream.chunks():
            destination.write(chunk)

        props = blob_client.get_blob_properties()
        return StorageFile(
            key=key,
            size=props.size,
            content_type=props.content_settings.content_type if props.content_settings else None,
            etag=props.etag,
            last_modified=props.last_modified,
            metadata=props.metadata or {},
        )

    async def download_bytes(self, key: str) -> bytes:
        """Download blob as bytes."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        blob_client = self._container_client.get_blob_client(key)
        download_stream = blob_client.download_blob()
        return download_stream.readall()

    async def stream_download(
        self,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream blob content."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        blob_client = self._container_client.get_blob_client(key)
        download_stream = blob_client.download_blob()

        for chunk in download_stream.chunks():
            # Yield in smaller chunks if needed
            for i in range(0, len(chunk), chunk_size):
                yield chunk[i : i + chunk_size]

    async def get_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: str | None = None,
    ) -> str:
        """Generate SAS URL for download."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        blob_client = self._container_client.get_blob_client(key)

        # Generate SAS token
        sas_token = generate_blob_sas(
            account_name=self._client.account_name,
            container_name=self.config.bucket,
            blob_name=key,
            account_key=self.config.access_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(UTC) + timedelta(seconds=expires_in),
            content_disposition=f'attachment; filename="{filename}"' if filename else None,
        )

        return f"{blob_client.url}?{sas_token}"

    async def exists(self, key: str) -> bool:
        """Check if blob exists."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        blob_client = self._container_client.get_blob_client(key)
        return blob_client.exists()

    async def get_metadata(self, key: str) -> StorageFile:
        """Get blob metadata."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        blob_client = self._container_client.get_blob_client(key)
        props = blob_client.get_blob_properties()

        return StorageFile(
            key=key,
            size=props.size,
            content_type=props.content_settings.content_type if props.content_settings else None,
            etag=props.etag,
            last_modified=props.last_modified,
            metadata=props.metadata or {},
        )

    async def delete(self, key: str) -> bool:
        """Delete a blob."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        try:
            blob_client = self._container_client.get_blob_client(key)
            blob_client.delete_blob()
            return True
        except Exception as e:
            logger.error("Failed to delete %s: %s", key, e)
            return False

    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple blobs."""
        if not self._container_client or not keys:
            return {}

        results = {}
        for key in keys:
            results[key] = await self.delete(key)

        return results

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Copy a blob within container."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        source_blob = self._container_client.get_blob_client(source_key)
        dest_blob = self._container_client.get_blob_client(dest_key)

        dest_blob.start_copy_from_url(source_blob.url)

        # Wait for copy to complete
        props = dest_blob.get_blob_properties()
        while props.copy.status == "pending":
            import time

            time.sleep(0.5)
            props = dest_blob.get_blob_properties()

        if props.copy.status != "success":
            raise RuntimeError(f"Copy failed: {props.copy.status}")

        return StorageFile(
            key=dest_key,
            size=props.size,
            content_type=props.content_settings.content_type if props.content_settings else None,
            etag=props.etag,
            last_modified=props.last_modified,
            metadata=props.metadata or {},
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
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        kwargs: dict[str, Any] = {}
        if prefix:
            kwargs["name_starts_with"] = prefix

        files = []
        count = 0

        # Use the continuation marker pattern
        blobs = self._container_client.list_blobs(**kwargs)

        for blob in blobs:
            if continuation_token and blob.name <= continuation_token:
                continue

            files.append(
                StorageFile(
                    key=blob.name,
                    size=blob.size,
                    content_type=(
                        blob.content_settings.content_type if blob.content_settings else None
                    ),
                    etag=blob.etag,
                    last_modified=blob.last_modified,
                    metadata=blob.metadata or {},
                )
            )

            count += 1
            if limit and count >= limit:
                return files, blob.name

        return files, None

    async def get_stats(self, prefix: str = "") -> StorageStats:
        """Get storage statistics."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        total_files = 0
        total_size = 0

        kwargs: dict[str, Any] = {}
        if prefix:
            kwargs["name_starts_with"] = prefix

        for blob in self._container_client.list_blobs(**kwargs):
            total_files += 1
            total_size += blob.size

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
        """Generate SAS URL for direct upload."""
        if not self._container_client:
            raise RuntimeError("Azure client not connected")

        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        blob_client = self._container_client.get_blob_client(key)

        permissions = BlobSasPermissions(write=True, create=True)

        sas_token = generate_blob_sas(
            account_name=self._client.account_name,
            container_name=self.config.bucket,
            blob_name=key,
            account_key=self.config.access_key,
            permission=permissions,
            expiry=datetime.now(UTC) + timedelta(seconds=expires_in),
        )

        return f"{blob_client.url}?{sas_token}"
