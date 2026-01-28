"""Cloud storage adapters for Eleanor evidence management.

Provides unified interface for local, S3, Azure Blob, and GCS storage.
"""

from app.adapters.storage.base import (
    StorageAdapter,
    StorageConfig,
    StorageFile,
    StorageStats,
)

__all__ = [
    "StorageAdapter",
    "StorageConfig",
    "StorageFile",
    "StorageStats",
    "get_storage_adapter",
]


_storage_adapter: StorageAdapter | None = None


def get_storage_adapter() -> StorageAdapter:
    """Get the configured storage adapter instance.

    Call init_storage_adapter() first during app startup.
    """
    if _storage_adapter is None:
        raise RuntimeError("Storage adapter not initialized. Call init_storage_adapter() first.")
    return _storage_adapter


async def init_storage_adapter(settings: object) -> StorageAdapter:
    """Initialize the storage adapter from application settings.

    Args:
        settings: Application settings object with storage configuration.

    Returns:
        Configured StorageAdapter instance.
    """
    global _storage_adapter

    backend = getattr(settings, "storage_backend", "local")

    config = StorageConfig(
        backend=backend,
        bucket=getattr(settings, "storage_bucket", None),
        region=getattr(settings, "storage_region", None),
        access_key=getattr(settings, "storage_access_key", None),
        secret_key=getattr(settings, "storage_secret_key", None),
        endpoint_url=getattr(settings, "storage_endpoint_url", None),
        connection_string=getattr(settings, "storage_connection_string", None),
        local_path=getattr(settings, "evidence_path", "/app/evidence"),
    )

    if backend == "s3":
        from app.adapters.storage.s3 import S3StorageAdapter

        _storage_adapter = S3StorageAdapter(config)
    elif backend == "azure":
        from app.adapters.storage.azure import AzureBlobStorageAdapter

        _storage_adapter = AzureBlobStorageAdapter(config)
    elif backend == "gcs":
        from app.adapters.storage.gcs import GCSStorageAdapter

        _storage_adapter = GCSStorageAdapter(config)
    else:
        from app.adapters.storage.local import LocalStorageAdapter

        _storage_adapter = LocalStorageAdapter(config)

    await _storage_adapter.connect()
    return _storage_adapter
