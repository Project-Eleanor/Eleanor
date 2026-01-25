"""Data connector models for Eleanor."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ConnectorType(str, enum.Enum):
    """Data connector types."""

    SYSLOG = "syslog"
    WINDOWS_EVENT = "windows_event"
    CLOUD_TRAIL = "cloud_trail"
    AZURE_AD = "azure_ad"
    OFFICE_365 = "office_365"
    AWS_S3 = "aws_s3"
    BEATS = "beats"
    KAFKA = "kafka"
    WEBHOOK = "webhook"
    API_POLLING = "api_polling"
    FILE_UPLOAD = "file_upload"
    CUSTOM = "custom"


class ConnectorStatus(str, enum.Enum):
    """Connector status."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    CONFIGURING = "configuring"


class ConnectorHealth(str, enum.Enum):
    """Connector health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class DataConnector(Base):
    """Data connector configuration model."""

    __tablename__ = "data_connectors"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Connector type and status
    connector_type: Mapped[ConnectorType] = mapped_column(
        Enum(ConnectorType), nullable=False
    )
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus), nullable=False, default=ConnectorStatus.DISABLED
    )
    health: Mapped[ConnectorHealth] = mapped_column(
        Enum(ConnectorHealth), nullable=False, default=ConnectorHealth.UNKNOWN
    )

    # Configuration (encrypted sensitive fields)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    # config contains type-specific settings:
    # - syslog: {host, port, protocol, format}
    # - windows_event: {hosts, channels, use_kerberos}
    # - cloud_trail: {aws_region, s3_bucket, role_arn}
    # - azure_ad: {tenant_id, client_id, client_secret}
    # - office_365: {tenant_id, client_id, client_secret, content_types}
    # - aws_s3: {bucket, region, access_key, secret_key, prefix}
    # - beats: {host, port, ssl_enabled}
    # - kafka: {bootstrap_servers, topics, consumer_group}
    # - webhook: {endpoint_path, auth_type, auth_token}
    # - api_polling: {base_url, auth_type, polling_interval}

    # Data routing
    target_index: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Examples: windows_security, linux_syslog, cloud_audit, etc.

    # Parsing configuration
    parser_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    # parser_config: {format, timestamp_field, custom_grok, field_mappings}

    # Filtering
    include_filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    exclude_filters: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Scheduling (for polling connectors)
    polling_interval: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # seconds

    # Statistics
    events_received: Mapped[int] = mapped_column(BigInteger, default=0)
    events_processed: Mapped[int] = mapped_column(BigInteger, default=0)
    events_failed: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0)

    # Health tracking
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    tags: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Tracking
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    creator: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<DataConnector {self.name} ({self.connector_type.value})>"


class ConnectorEvent(Base):
    """Connector event log for tracking significant events."""

    __tablename__ = "connector_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_connectors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # started, stopped, error, config_changed, health_changed

    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<ConnectorEvent {self.event_type} for {self.connector_id}>"
