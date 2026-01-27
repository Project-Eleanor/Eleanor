"""Eleanor configuration management."""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Eleanor"
    app_version: str = "1.0.0-alpha"
    debug: bool = False
    testing: bool = False  # Skip tenant DB lookups in tests
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://eleanor:eleanor@localhost:5432/eleanor"

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_prefix: str = "eleanor"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Security
    secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:4200"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Authentication Providers
    # OIDC
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:4200/auth/callback"

    # LDAP
    ldap_enabled: bool = False
    ldap_server: str = ""
    ldap_base_dn: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_user_filter: str = "(sAMAccountName={username})"
    ldap_group_filter: str = "(member={user_dn})"

    # SAM (Local Accounts)
    sam_enabled: bool = True
    sam_allow_registration: bool = False

    # Evidence Storage
    evidence_path: str = "/app/evidence"

    # Cloud Storage Settings
    storage_backend: str = "local"  # local, s3, azure, gcs
    storage_bucket: str | None = None  # Bucket/container name for cloud storage
    storage_region: str | None = None  # AWS region or equivalent
    storage_access_key: str | None = None  # Access key or service account path (GCS)
    storage_secret_key: str | None = None  # Secret key
    storage_endpoint_url: str | None = None  # For S3-compatible (MinIO) or Azure account URL
    storage_connection_string: str | None = None  # Azure connection string

    # Case Number Format
    case_number_prefix: str = "ELEANOR"

    # ==========================================================================
    # Integration Settings
    # ==========================================================================

    # Velociraptor - Endpoint Collection
    velociraptor_enabled: bool = False
    velociraptor_url: str = "https://localhost:8003"
    velociraptor_api_key: str = ""
    velociraptor_verify_ssl: bool = True
    velociraptor_client_cert: str = ""
    velociraptor_client_key: str = ""
    velociraptor_ca_cert: str = ""
    velociraptor_grpc_server_name: str = "VelociraptorServer"
    velociraptor_username: str = ""
    velociraptor_password: str = ""

    # IRIS - Case Management
    iris_enabled: bool = False
    iris_url: str = "https://localhost:8443"
    iris_api_key: str = ""
    iris_verify_ssl: bool = False  # IRIS uses self-signed certs by default

    # OpenCTI - Threat Intelligence
    opencti_enabled: bool = False
    opencti_url: str = "http://localhost:8080"
    opencti_api_key: str = ""
    opencti_verify_ssl: bool = True

    # Shuffle - SOAR / Workflow Automation
    shuffle_enabled: bool = False
    shuffle_url: str = "http://localhost:3001"
    shuffle_api_key: str = ""
    shuffle_verify_ssl: bool = True

    # Timesketch - Timeline Analysis
    timesketch_enabled: bool = False
    timesketch_url: str = "http://localhost:5000"
    timesketch_api_key: str = ""
    timesketch_verify_ssl: bool = True
    timesketch_username: str = ""
    timesketch_password: str = ""

    # Microsoft Defender for Endpoint
    defender_enabled: bool = False
    defender_tenant_id: str = ""  # Azure AD tenant ID
    defender_client_id: str = ""  # Application (client) ID
    defender_client_secret: str = ""  # Client secret

    # Microsoft Sentinel
    sentinel_enabled: bool = False
    sentinel_tenant_id: str = ""  # Azure AD tenant ID
    sentinel_client_id: str = ""  # Application (client) ID
    sentinel_client_secret: str = ""  # Client secret
    sentinel_subscription_id: str = ""  # Azure subscription ID
    sentinel_resource_group: str = ""  # Resource group containing Sentinel workspace
    sentinel_workspace_name: str = ""  # Log Analytics workspace name


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
