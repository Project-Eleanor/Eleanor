"""AWS S3 storage adapter for Eleanor evidence.

Provides storage operations using Amazon S3 or S3-compatible storage
(MinIO, DigitalOcean Spaces, Wasabi, etc.).
"""

import hashlib
import logging
from collections.abc import AsyncIterator
from io import BytesIO
from typing import Any, BinaryIO

from app.adapters.storage.base import (
    StorageAdapter,
    StorageConfig,
    StorageFile,
    StorageStats,
    UploadResult,
)

logger = logging.getLogger(__name__)


class S3StorageAdapter(StorageAdapter):
    """AWS S3 storage adapter.

    Supports AWS S3 and S3-compatible storage backends.
    Uses boto3 for all S3 operations with async wrappers.
    """

    name = "s3"

    def __init__(self, config: StorageConfig):
        """Initialize S3 storage adapter.

        Args:
            config: Storage configuration with bucket and credentials.
        """
        super().__init__(config)
        self._client = None
        self._resource = None

    async def connect(self) -> bool:
        """Initialize boto3 client and verify bucket access."""
        try:
            import boto3
            from botocore.config import Config as BotoConfig
            from botocore.exceptions import ClientError

            # Build client configuration
            client_kwargs: dict[str, Any] = {}

            if self.config.region:
                client_kwargs["region_name"] = self.config.region

            if self.config.access_key and self.config.secret_key:
                client_kwargs["aws_access_key_id"] = self.config.access_key
                client_kwargs["aws_secret_access_key"] = self.config.secret_key

            if self.config.endpoint_url:
                client_kwargs["endpoint_url"] = self.config.endpoint_url

            # Configure for large file transfers
            boto_config = BotoConfig(
                max_pool_connections=self.config.max_concurrency,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )
            client_kwargs["config"] = boto_config

            self._client = boto3.client("s3", **client_kwargs)
            self._resource = boto3.resource("s3", **client_kwargs)

            # Verify bucket exists and is accessible
            try:
                self._client.head_bucket(Bucket=self.config.bucket)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code == "404":
                    logger.error("S3 bucket not found: %s", self.config.bucket)
                    return False
                elif error_code == "403":
                    logger.error("Access denied to S3 bucket: %s", self.config.bucket)
                    return False
                raise

            self._connected = True
            logger.info("S3 storage connected: %s", self.config.bucket)
            return True

        except ImportError:
            logger.error("boto3 not installed. Run: pip install boto3")
            return False
        except Exception as e:
            logger.error("Failed to connect to S3: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close S3 client."""
        self._client = None
        self._resource = None
        self._connected = False

    async def health_check(self) -> dict[str, Any]:
        """Check S3 storage health."""
        if not self._client:
            return {"status": "disconnected", "backend": "s3"}

        try:
            self._client.head_bucket(Bucket=self.config.bucket)
            return {
                "status": "healthy",
                "backend": "s3",
                "bucket": self.config.bucket,
                "region": self.config.region,
                "endpoint": self.config.endpoint_url,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "s3",
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
        if not self._client:
            raise RuntimeError("S3 client not connected")

        # Read file and compute hashes
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

        # Prepare upload kwargs
        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata

        # Upload using multipart for large files
        if size >= self.config.multipart_threshold:
            await self._multipart_upload(data, key, extra_args)
        else:
            self._client.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=data,
                **extra_args,
            )

        return UploadResult(
            key=key,
            size=size,
            sha256=sha256.hexdigest(),
            sha1=sha1.hexdigest(),
            md5=md5.hexdigest(),
            content_type=content_type,
            storage_url=f"s3://{self.config.bucket}/{key}",
        )

    async def _multipart_upload(
        self,
        data: bytes,
        key: str,
        extra_args: dict[str, Any],
    ) -> None:
        """Perform multipart upload for large files."""
        from boto3.s3.transfer import TransferConfig

        config = TransferConfig(
            multipart_threshold=self.config.multipart_threshold,
            multipart_chunksize=self.config.multipart_chunksize,
            max_concurrency=self.config.max_concurrency,
        )

        bucket = self._resource.Bucket(self.config.bucket)
        bucket.upload_fileobj(
            BytesIO(data),
            key,
            ExtraArgs=extra_args if extra_args else None,
            Config=config,
        )

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload bytes to S3."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        sha256 = hashlib.sha256(data).hexdigest()
        sha1 = hashlib.sha1(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()

        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata

        if len(data) >= self.config.multipart_threshold:
            await self._multipart_upload(data, key, extra_args)
        else:
            self._client.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=data,
                **extra_args,
            )

        return UploadResult(
            key=key,
            size=len(data),
            sha256=sha256,
            sha1=sha1,
            md5=md5,
            content_type=content_type,
            storage_url=f"s3://{self.config.bucket}/{key}",
        )

    async def download_file(
        self,
        key: str,
        destination: BinaryIO,
    ) -> StorageFile:
        """Download file from S3."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        response = self._client.get_object(
            Bucket=self.config.bucket,
            Key=key,
        )

        body = response["Body"]
        while chunk := body.read(8192):
            destination.write(chunk)

        return StorageFile(
            key=key,
            size=response["ContentLength"],
            content_type=response.get("ContentType"),
            etag=response.get("ETag", "").strip('"'),
            last_modified=response.get("LastModified"),
            metadata=response.get("Metadata", {}),
        )

    async def download_bytes(self, key: str) -> bytes:
        """Download file as bytes."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        response = self._client.get_object(
            Bucket=self.config.bucket,
            Key=key,
        )
        return response["Body"].read()

    async def stream_download(
        self,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream file content."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        response = self._client.get_object(
            Bucket=self.config.bucket,
            Key=key,
        )

        body = response["Body"]
        while chunk := body.read(chunk_size):
            yield chunk

    async def get_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: str | None = None,
    ) -> str:
        """Generate presigned download URL."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        params = {
            "Bucket": self.config.bucket,
            "Key": key,
        }

        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        return self._client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    async def exists(self, key: str) -> bool:
        """Check if object exists."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        try:
            self._client.head_object(Bucket=self.config.bucket, Key=key)
            return True
        except self._client.exceptions.NoSuchKey:
            return False
        except Exception:
            return False

    async def get_metadata(self, key: str) -> StorageFile:
        """Get object metadata."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        response = self._client.head_object(
            Bucket=self.config.bucket,
            Key=key,
        )

        return StorageFile(
            key=key,
            size=response["ContentLength"],
            content_type=response.get("ContentType"),
            etag=response.get("ETag", "").strip('"'),
            last_modified=response.get("LastModified"),
            metadata=response.get("Metadata", {}),
        )

    async def delete(self, key: str) -> bool:
        """Delete an object."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        try:
            self._client.delete_object(
                Bucket=self.config.bucket,
                Key=key,
            )
            return True
        except Exception as e:
            logger.error("Failed to delete %s: %s", key, e)
            return False

    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple objects."""
        if not self._client or not keys:
            return {}

        # S3 delete_objects supports up to 1000 keys per request
        results = {key: False for key in keys}

        for i in range(0, len(keys), 1000):
            batch = keys[i:i + 1000]
            try:
                response = self._client.delete_objects(
                    Bucket=self.config.bucket,
                    Delete={
                        "Objects": [{"Key": key} for key in batch],
                        "Quiet": False,
                    },
                )

                # Mark successfully deleted
                for deleted in response.get("Deleted", []):
                    results[deleted["Key"]] = True

                # Log errors
                for error in response.get("Errors", []):
                    logger.error(
                        "Failed to delete %s: %s",
                        error["Key"],
                        error.get("Message"),
                    )

            except Exception as e:
                logger.error("Batch delete failed: %s", e)

        return results

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Copy an object within S3."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        copy_source = {"Bucket": self.config.bucket, "Key": source_key}

        self._client.copy_object(
            Bucket=self.config.bucket,
            Key=dest_key,
            CopySource=copy_source,
        )

        return await self.get_metadata(dest_key)

    async def move(
        self,
        source_key: str,
        dest_key: str,
    ) -> StorageFile:
        """Move an object (copy + delete)."""
        result = await self.copy(source_key, dest_key)
        await self.delete(source_key)
        return result

    async def list_files(
        self,
        prefix: str = "",
        limit: int | None = None,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageFile], str | None]:
        """List objects with prefix."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        kwargs: dict[str, Any] = {
            "Bucket": self.config.bucket,
        }

        if prefix:
            kwargs["Prefix"] = prefix
        if limit:
            kwargs["MaxKeys"] = limit
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = self._client.list_objects_v2(**kwargs)

        files = [
            StorageFile(
                key=obj["Key"],
                size=obj["Size"],
                etag=obj.get("ETag", "").strip('"'),
                last_modified=obj.get("LastModified"),
            )
            for obj in response.get("Contents", [])
        ]

        next_token = response.get("NextContinuationToken")
        return files, next_token

    async def get_stats(self, prefix: str = "") -> StorageStats:
        """Get storage statistics."""
        if not self._client:
            raise RuntimeError("S3 client not connected")

        total_files = 0
        total_size = 0
        continuation_token = None

        while True:
            kwargs: dict[str, Any] = {
                "Bucket": self.config.bucket,
            }
            if prefix:
                kwargs["Prefix"] = prefix
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = self._client.list_objects_v2(**kwargs)

            for obj in response.get("Contents", []):
                total_files += 1
                total_size += obj["Size"]

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

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
        """Generate presigned upload URL for direct uploads.

        Useful for browser-based uploads that bypass the backend.
        """
        if not self._client:
            raise RuntimeError("S3 client not connected")

        params = {
            "Bucket": self.config.bucket,
            "Key": key,
        }

        if content_type:
            params["ContentType"] = content_type

        return self._client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_in,
        )
