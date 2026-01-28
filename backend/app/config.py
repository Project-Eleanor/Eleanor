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
        return list(v) if v else []

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

    # ==========================================================================
    # Phase 1: Enrichment and Notifications
    # ==========================================================================

    # VirusTotal - File/IOC Enrichment
    virustotal_enabled: bool = False
    virustotal_api_key: str = ""
    virustotal_rate_limit: int = 4  # Requests per minute (free tier)

    # Slack - Notifications
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    slack_bot_token: str = ""
    slack_default_channel: str = "#dfir-alerts"

    # Microsoft Teams - Notifications
    teams_enabled: bool = False
    teams_webhook_url: str = ""

    # ==========================================================================
    # Phase 2: Cloud and Identity Integrations
    # ==========================================================================

    # GCP Cloud Logging
    gcp_enabled: bool = False
    gcp_project_id: str = ""
    gcp_credentials_path: str = ""
    gcp_default_log_name: str = ""

    # AWS Security Hub
    aws_securityhub_enabled: bool = False
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    # Okta - Identity Management
    okta_enabled: bool = False
    okta_domain: str = ""  # e.g., dev-123456.okta.com
    okta_api_token: str = ""

    # MISP - Threat Intelligence
    misp_enabled: bool = False
    misp_url: str = ""
    misp_api_key: str = ""
    misp_verify_ssl: bool = True

    # ==========================================================================
    # Phase 3: EDR and Case Management
    # ==========================================================================

    # CrowdStrike Falcon
    crowdstrike_enabled: bool = False
    crowdstrike_client_id: str = ""
    crowdstrike_client_secret: str = ""
    crowdstrike_region: str = "us-1"  # us-1, us-2, eu-1, us-gov-1

    # TheHive - Case Management
    thehive_enabled: bool = False
    thehive_url: str = ""
    thehive_api_key: str = ""
    thehive_organisation: str = ""
    thehive_verify_ssl: bool = True

    # Cortex - Analysis/Response
    cortex_enabled: bool = False
    cortex_url: str = ""
    cortex_api_key: str = ""
    cortex_organisation: str = ""
    cortex_verify_ssl: bool = True

    # Jira - Ticketing
    jira_enabled: bool = False
    jira_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    jira_default_project: str = ""
    jira_default_issue_type: str = "Task"
    jira_case_link_field: str = ""  # Custom field ID for case links

    # ==========================================================================
    # Phase 4: SIEM and Advanced Integrations
    # ==========================================================================

    # Splunk - SIEM (Bidirectional)
    splunk_enabled: bool = False
    splunk_url: str = ""  # Management port (8089)
    splunk_username: str = ""
    splunk_password: str = ""
    splunk_hec_url: str = ""  # HEC port (8088)
    splunk_hec_token: str = ""
    splunk_default_index: str = "main"
    splunk_verify_ssl: bool = True

    # Azure Event Hub
    eventhub_enabled: bool = False
    eventhub_connection_string: str = ""
    eventhub_name: str = ""
    eventhub_consumer_group: str = "$Default"
    eventhub_checkpoint_connection_string: str = ""
    eventhub_checkpoint_container: str = "eventhub-checkpoints"

    # Fluentd/Fluent Bit
    fluentd_enabled: bool = False
    fluentd_http_port: int = 8888
    fluentd_forward_enabled: bool = False
    fluentd_forward_port: int = 24224

    # Windows Event Forwarding (WEF)
    wef_enabled: bool = False
    wef_port: int = 5985
    wef_use_https: bool = False
    wef_https_port: int = 5986

    # ==========================================================================
    # Detection Engines
    # ==========================================================================

    # YARA
    yara_enabled: bool = True
    yara_rules_path: str = "/app/yara-rules"
    yara_compiled_rules_path: str = ""

    # Sigma
    sigma_enabled: bool = True
    sigma_rules_path: str = "/app/sigma-rules"
    sigma_pipeline: str = "ecs_windows"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
