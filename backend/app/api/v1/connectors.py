"""Data connectors management API endpoints."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.connector import (
    ConnectorEvent,
    ConnectorHealth,
    ConnectorStatus,
    ConnectorType,
    DataConnector,
)
from app.models.user import User

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class ConnectorCreate(BaseModel):
    """Create data connector request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    connector_type: ConnectorType
    config: dict = {}
    target_index: str | None = None
    data_type: str | None = None
    parser_config: dict = {}
    include_filters: dict = {}
    exclude_filters: dict = {}
    polling_interval: int | None = Field(None, ge=10, le=86400)
    tags: dict = {}


class ConnectorUpdate(BaseModel):
    """Update data connector request."""

    name: str | None = None
    description: str | None = None
    config: dict | None = None
    target_index: str | None = None
    data_type: str | None = None
    parser_config: dict | None = None
    include_filters: dict | None = None
    exclude_filters: dict | None = None
    polling_interval: int | None = None
    tags: dict | None = None


class ConnectorResponse(BaseModel):
    """Data connector response."""

    id: UUID
    name: str
    description: str | None
    connector_type: ConnectorType
    status: ConnectorStatus
    health: ConnectorHealth
    config: dict
    target_index: str | None
    data_type: str | None
    parser_config: dict
    include_filters: dict
    exclude_filters: dict
    polling_interval: int | None
    events_received: int
    events_processed: int
    events_failed: int
    bytes_received: int
    last_event_at: datetime | None
    last_error_at: datetime | None
    last_error_message: str | None
    last_health_check_at: datetime | None
    tags: dict
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectorListResponse(BaseModel):
    """Paginated connector list response."""

    items: list[ConnectorResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ConnectorEventResponse(BaseModel):
    """Connector event response."""

    id: UUID
    connector_id: UUID
    event_type: str
    message: str | None
    details: dict
    created_at: datetime

    class Config:
        from_attributes = True


class TestResult(BaseModel):
    """Connector test result."""

    success: bool
    message: str
    latency_ms: int | None = None
    details: dict = {}


# =============================================================================
# Helper Functions
# =============================================================================


def mask_sensitive_config(config: dict, connector_type: ConnectorType) -> dict:
    """Mask sensitive fields in connector configuration."""
    sensitive_fields = {
        "client_secret",
        "secret_key",
        "api_key",
        "password",
        "auth_token",
        "private_key",
    }

    masked = {}
    for key, value in config.items():
        if key.lower() in sensitive_fields and value:
            masked[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_config(value, connector_type)
        else:
            masked[key] = value
    return masked


async def log_connector_event(
    db: AsyncSession,
    connector_id: UUID,
    event_type: str,
    message: str | None = None,
    details: dict | None = None,
) -> None:
    """Log a connector event."""
    event = ConnectorEvent(
        connector_id=connector_id,
        event_type=event_type,
        message=message,
        details=details or {},
    )
    db.add(event)


async def test_connector_connectivity(
    connector: DataConnector,
) -> TestResult:
    """Test actual connectivity for a data connector based on its type.

    Performs real connectivity tests appropriate for each connector type:
    - Socket-based: TCP connection test
    - API-based: HTTP endpoint health check
    - Passive receivers: Configuration validation only
    """
    import asyncio
    import socket
    import ssl
    import time

    config = connector.config or {}
    start_time = time.time()
    details: dict[str, Any] = {
        "connector_type": connector.connector_type.value,
        "target_index": connector.target_index,
    }

    try:
        if connector.connector_type == ConnectorType.SYSLOG:
            # Test TCP/UDP connectivity to syslog receiver
            host = config.get("host", "localhost")
            port = config.get("port", 514)
            protocol = config.get("protocol", "tcp").lower()

            if protocol == "tcp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((host, port))
                sock.close()
            else:
                # UDP - just verify DNS resolution and port config
                socket.getaddrinfo(host, port)

            details["host"] = host
            details["port"] = port
            details["protocol"] = protocol

        elif connector.connector_type == ConnectorType.WINDOWS_EVENT:
            # Test WinRM connectivity to Windows hosts
            hosts = config.get("hosts", [])
            if not hosts:
                return TestResult(
                    success=False,
                    message="No Windows hosts configured",
                    details=details,
                )

            # Test first host connectivity on WinRM port (5985/5986)
            test_host = hosts[0] if isinstance(hosts, list) else hosts
            winrm_port = 5986 if config.get("use_ssl", True) else 5985

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((test_host, winrm_port))
            sock.close()

            details["tested_host"] = test_host
            details["winrm_port"] = winrm_port
            details["total_hosts"] = len(hosts) if isinstance(hosts, list) else 1

        elif connector.connector_type in (ConnectorType.CLOUD_TRAIL, ConnectorType.AWS_S3):
            # Test AWS connectivity via S3 bucket listing
            import httpx

            region = config.get("aws_region", config.get("region", "us-east-1"))
            bucket = config.get("s3_bucket", config.get("bucket"))

            if not bucket:
                return TestResult(
                    success=False,
                    message="No S3 bucket configured",
                    details=details,
                )

            # Test S3 endpoint reachability (actual auth requires boto3)
            endpoint = f"https://s3.{region}.amazonaws.com"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(endpoint)
                # S3 returns 405 for HEAD without auth, but connection works
                if response.status_code not in (200, 403, 405):
                    return TestResult(
                        success=False,
                        message=f"S3 endpoint returned {response.status_code}",
                        latency_ms=int((time.time() - start_time) * 1000),
                        details=details,
                    )

            details["region"] = region
            details["bucket"] = bucket
            details["endpoint"] = endpoint

        elif connector.connector_type in (ConnectorType.AZURE_AD, ConnectorType.OFFICE_365):
            # Test Microsoft Graph API / Management API connectivity
            import httpx

            tenant_id = config.get("tenant_id")
            if not tenant_id:
                return TestResult(
                    success=False,
                    message="No tenant_id configured",
                    details=details,
                )

            # Test Microsoft login endpoint reachability
            endpoint = f"https://login.microsoftonline.com/{tenant_id}/.well-known/openid-configuration"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint)
                if response.status_code != 200:
                    return TestResult(
                        success=False,
                        message=f"Azure AD endpoint returned {response.status_code}",
                        latency_ms=int((time.time() - start_time) * 1000),
                        details=details,
                    )

            details["tenant_id"] = tenant_id[:8] + "..." if len(tenant_id) > 8 else tenant_id

        elif connector.connector_type == ConnectorType.BEATS:
            # Test Elasticsearch beats index pattern exists
            host = config.get("host", "localhost")
            port = config.get("port", 5044)

            # Test Logstash beats input port connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()

            details["host"] = host
            details["port"] = port

        elif connector.connector_type == ConnectorType.KAFKA:
            # Test Kafka broker connectivity
            bootstrap_servers = config.get("bootstrap_servers", "localhost:9092")
            servers = bootstrap_servers.split(",") if isinstance(bootstrap_servers, str) else bootstrap_servers

            if not servers:
                return TestResult(
                    success=False,
                    message="No Kafka bootstrap servers configured",
                    details=details,
                )

            # Test first broker connectivity
            first_server = servers[0].strip()
            if ":" in first_server:
                host, port_str = first_server.rsplit(":", 1)
                port = int(port_str)
            else:
                host, port = first_server, 9092

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()

            details["tested_broker"] = first_server
            details["total_brokers"] = len(servers)
            details["topics"] = config.get("topics", [])

        elif connector.connector_type == ConnectorType.API_POLLING:
            # Test polling target URL
            import httpx

            base_url = config.get("base_url")
            if not base_url:
                return TestResult(
                    success=False,
                    message="No base_url configured for API polling",
                    details=details,
                )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(base_url, follow_redirects=True)
                if response.status_code >= 500:
                    return TestResult(
                        success=False,
                        message=f"API endpoint returned server error: {response.status_code}",
                        latency_ms=int((time.time() - start_time) * 1000),
                        details=details,
                    )

            details["base_url"] = base_url
            details["response_code"] = response.status_code

        elif connector.connector_type == ConnectorType.WEBHOOK:
            # Passive receiver - validate configuration only
            endpoint_path = config.get("endpoint_path", "/webhook")
            auth_type = config.get("auth_type", "none")

            if not endpoint_path:
                return TestResult(
                    success=False,
                    message="No endpoint_path configured for webhook",
                    details=details,
                )

            details["endpoint_path"] = endpoint_path
            details["auth_type"] = auth_type
            details["note"] = "Webhook is a passive receiver - configuration validated"

        elif connector.connector_type == ConnectorType.FILE_UPLOAD:
            # Passive - configuration validation only
            details["note"] = "File upload is a passive receiver - no connectivity test required"

        elif connector.connector_type == ConnectorType.CUSTOM:
            # Custom connectors - attempt generic connectivity if host/port provided
            host = config.get("host")
            port = config.get("port")

            if host and port:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((host, int(port)))
                sock.close()
                details["host"] = host
                details["port"] = port
            else:
                details["note"] = "Custom connector - no host/port for connectivity test"

        latency_ms = int((time.time() - start_time) * 1000)
        return TestResult(
            success=True,
            message="Connection test successful",
            latency_ms=latency_ms,
            details=details,
        )

    except socket.timeout:
        return TestResult(
            success=False,
            message="Connection timed out",
            latency_ms=int((time.time() - start_time) * 1000),
            details=details,
        )
    except socket.gaierror as e:
        return TestResult(
            success=False,
            message=f"DNS resolution failed: {e}",
            latency_ms=int((time.time() - start_time) * 1000),
            details=details,
        )
    except ConnectionRefusedError:
        return TestResult(
            success=False,
            message="Connection refused by target host",
            latency_ms=int((time.time() - start_time) * 1000),
            details=details,
        )
    except Exception as e:
        return TestResult(
            success=False,
            message=f"Connection test failed: {str(e)}",
            latency_ms=int((time.time() - start_time) * 1000),
            details=details,
        )


# =============================================================================
# Endpoints - Connector Management
# =============================================================================


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    connector_type: ConnectorType | None = Query(None, alias="type"),
    status_filter: ConnectorStatus | None = Query(None, alias="status"),
    health: ConnectorHealth | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ConnectorListResponse:
    """List data connectors with filtering and pagination."""
    query = select(DataConnector)

    # Apply filters
    if connector_type:
        query = query.where(DataConnector.connector_type == connector_type)
    if status_filter:
        query = query.where(DataConnector.status == status_filter)
    if health:
        query = query.where(DataConnector.health == health)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (DataConnector.name.ilike(search_filter))
            | (DataConnector.description.ilike(search_filter))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(DataConnector.name)

    result = await db.execute(query)
    connectors = result.scalars().all()

    items = [
        ConnectorResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            connector_type=c.connector_type,
            status=c.status,
            health=c.health,
            config=mask_sensitive_config(c.config, c.connector_type),
            target_index=c.target_index,
            data_type=c.data_type,
            parser_config=c.parser_config,
            include_filters=c.include_filters,
            exclude_filters=c.exclude_filters,
            polling_interval=c.polling_interval,
            events_received=c.events_received,
            events_processed=c.events_processed,
            events_failed=c.events_failed,
            bytes_received=c.bytes_received,
            last_event_at=c.last_event_at,
            last_error_at=c.last_error_at,
            last_error_message=c.last_error_message,
            last_health_check_at=c.last_health_check_at,
            tags=c.tags,
            created_by=c.created_by,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in connectors
    ]

    pages = (total + page_size - 1) // page_size if page_size else 1

    return ConnectorListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    """Get data connector by ID."""
    query = select(DataConnector).where(DataConnector.id == connector_id)
    result = await db.execute(query)
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        description=connector.description,
        connector_type=connector.connector_type,
        status=connector.status,
        health=connector.health,
        config=mask_sensitive_config(connector.config, connector.connector_type),
        target_index=connector.target_index,
        data_type=connector.data_type,
        parser_config=connector.parser_config,
        include_filters=connector.include_filters,
        exclude_filters=connector.exclude_filters,
        polling_interval=connector.polling_interval,
        events_received=connector.events_received,
        events_processed=connector.events_processed,
        events_failed=connector.events_failed,
        bytes_received=connector.bytes_received,
        last_event_at=connector.last_event_at,
        last_error_at=connector.last_error_at,
        last_error_message=connector.last_error_message,
        last_health_check_at=connector.last_health_check_at,
        tags=connector.tags,
        created_by=connector.created_by,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    connector_data: ConnectorCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    """Create a new data connector."""
    connector = DataConnector(
        name=connector_data.name,
        description=connector_data.description,
        connector_type=connector_data.connector_type,
        status=ConnectorStatus.CONFIGURING,
        health=ConnectorHealth.UNKNOWN,
        config=connector_data.config,
        target_index=connector_data.target_index,
        data_type=connector_data.data_type,
        parser_config=connector_data.parser_config,
        include_filters=connector_data.include_filters,
        exclude_filters=connector_data.exclude_filters,
        polling_interval=connector_data.polling_interval,
        tags=connector_data.tags,
        created_by=current_user.id,
    )

    db.add(connector)
    await db.flush()

    # Log creation event
    await log_connector_event(
        db,
        connector.id,
        "created",
        f"Connector '{connector.name}' created",
        {"type": connector.connector_type.value},
    )

    await db.commit()
    await db.refresh(connector)

    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        description=connector.description,
        connector_type=connector.connector_type,
        status=connector.status,
        health=connector.health,
        config=mask_sensitive_config(connector.config, connector.connector_type),
        target_index=connector.target_index,
        data_type=connector.data_type,
        parser_config=connector.parser_config,
        include_filters=connector.include_filters,
        exclude_filters=connector.exclude_filters,
        polling_interval=connector.polling_interval,
        events_received=connector.events_received,
        events_processed=connector.events_processed,
        events_failed=connector.events_failed,
        bytes_received=connector.bytes_received,
        last_event_at=connector.last_event_at,
        last_error_at=connector.last_error_at,
        last_error_message=connector.last_error_message,
        last_health_check_at=connector.last_health_check_at,
        tags=connector.tags,
        created_by=connector.created_by,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


@router.patch("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    connector_id: UUID,
    updates: ConnectorUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    """Update a data connector."""
    query = select(DataConnector).where(DataConnector.id == connector_id)
    result = await db.execute(query)
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    changes = {}
    for field, value in update_data.items():
        if value is not None:
            old_value = getattr(connector, field)
            setattr(connector, field, value)
            if field != "config":  # Don't log config changes (may contain secrets)
                changes[field] = {"old": str(old_value), "new": str(value)}

    if changes:
        await log_connector_event(
            db,
            connector.id,
            "config_changed",
            "Connector configuration updated",
            {"changes": changes},
        )

    await db.commit()
    await db.refresh(connector)

    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        description=connector.description,
        connector_type=connector.connector_type,
        status=connector.status,
        health=connector.health,
        config=mask_sensitive_config(connector.config, connector.connector_type),
        target_index=connector.target_index,
        data_type=connector.data_type,
        parser_config=connector.parser_config,
        include_filters=connector.include_filters,
        exclude_filters=connector.exclude_filters,
        polling_interval=connector.polling_interval,
        events_received=connector.events_received,
        events_processed=connector.events_processed,
        events_failed=connector.events_failed,
        bytes_received=connector.bytes_received,
        last_event_at=connector.last_event_at,
        last_error_at=connector.last_error_at,
        last_error_message=connector.last_error_message,
        last_health_check_at=connector.last_health_check_at,
        tags=connector.tags,
        created_by=connector.created_by,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a data connector."""
    query = select(DataConnector).where(DataConnector.id == connector_id)
    result = await db.execute(query)
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    await db.delete(connector)
    await db.commit()


# =============================================================================
# Endpoints - Connector Actions
# =============================================================================


@router.post("/{connector_id}/enable", response_model=ConnectorResponse)
async def enable_connector(
    connector_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    """Enable a data connector."""
    query = select(DataConnector).where(DataConnector.id == connector_id)
    result = await db.execute(query)
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    connector.status = ConnectorStatus.ENABLED
    await log_connector_event(db, connector.id, "started", "Connector enabled")
    await db.commit()
    await db.refresh(connector)

    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        description=connector.description,
        connector_type=connector.connector_type,
        status=connector.status,
        health=connector.health,
        config=mask_sensitive_config(connector.config, connector.connector_type),
        target_index=connector.target_index,
        data_type=connector.data_type,
        parser_config=connector.parser_config,
        include_filters=connector.include_filters,
        exclude_filters=connector.exclude_filters,
        polling_interval=connector.polling_interval,
        events_received=connector.events_received,
        events_processed=connector.events_processed,
        events_failed=connector.events_failed,
        bytes_received=connector.bytes_received,
        last_event_at=connector.last_event_at,
        last_error_at=connector.last_error_at,
        last_error_message=connector.last_error_message,
        last_health_check_at=connector.last_health_check_at,
        tags=connector.tags,
        created_by=connector.created_by,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


@router.post("/{connector_id}/disable", response_model=ConnectorResponse)
async def disable_connector(
    connector_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    """Disable a data connector."""
    query = select(DataConnector).where(DataConnector.id == connector_id)
    result = await db.execute(query)
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    connector.status = ConnectorStatus.DISABLED
    await log_connector_event(db, connector.id, "stopped", "Connector disabled")
    await db.commit()
    await db.refresh(connector)

    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        description=connector.description,
        connector_type=connector.connector_type,
        status=connector.status,
        health=connector.health,
        config=mask_sensitive_config(connector.config, connector.connector_type),
        target_index=connector.target_index,
        data_type=connector.data_type,
        parser_config=connector.parser_config,
        include_filters=connector.include_filters,
        exclude_filters=connector.exclude_filters,
        polling_interval=connector.polling_interval,
        events_received=connector.events_received,
        events_processed=connector.events_processed,
        events_failed=connector.events_failed,
        bytes_received=connector.bytes_received,
        last_event_at=connector.last_event_at,
        last_error_at=connector.last_error_at,
        last_error_message=connector.last_error_message,
        last_health_check_at=connector.last_health_check_at,
        tags=connector.tags,
        created_by=connector.created_by,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


@router.post("/{connector_id}/test", response_model=TestResult)
async def test_connector(
    connector_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TestResult:
    """Test connectivity for a data connector.

    Performs actual connectivity tests based on connector type:
    - Syslog: TCP/UDP socket test to configured host:port
    - Windows Event: WinRM port connectivity test
    - CloudTrail/S3: AWS S3 endpoint reachability
    - Azure AD/Office 365: Microsoft Graph API health check
    - Beats: Logstash beats input port test
    - Kafka: Broker connectivity test
    - API Polling: Target URL health check
    - Webhook/File Upload: Configuration validation only
    """
    query = select(DataConnector).where(DataConnector.id == connector_id)
    result = await db.execute(query)
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    # Update health check timestamp
    connector.last_health_check_at = datetime.utcnow()

    # Perform actual connectivity test based on connector type
    test_result = await test_connector_connectivity(connector)

    # Log the test event
    await log_connector_event(
        db,
        connector_id,
        event_type="health_check",
        message=test_result.message,
        details={
            "success": test_result.success,
            "latency_ms": test_result.latency_ms,
        },
    )

    if test_result.success:
        connector.health = ConnectorHealth.HEALTHY
        connector.last_error_message = None
    else:
        connector.health = ConnectorHealth.UNHEALTHY
        connector.last_error_at = datetime.utcnow()
        connector.last_error_message = test_result.message

    await db.commit()

    return test_result


# =============================================================================
# Endpoints - Events and Statistics
# =============================================================================


@router.get("/{connector_id}/events", response_model=list[ConnectorEventResponse])
async def list_connector_events(
    connector_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
) -> list[ConnectorEventResponse]:
    """List events for a connector."""
    query = (
        select(ConnectorEvent)
        .where(ConnectorEvent.connector_id == connector_id)
        .order_by(ConnectorEvent.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    events = result.scalars().all()

    return [
        ConnectorEventResponse(
            id=e.id,
            connector_id=e.connector_id,
            event_type=e.event_type,
            message=e.message,
            details=e.details,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/stats/overview")
async def get_connectors_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Get overall connector statistics."""
    # Count by status
    status_query = select(
        DataConnector.status, func.count(DataConnector.id)
    ).group_by(DataConnector.status)
    status_result = await db.execute(status_query)
    status_counts = {row[0].value: row[1] for row in status_result.all()}

    # Count by health
    health_query = select(
        DataConnector.health, func.count(DataConnector.id)
    ).group_by(DataConnector.health)
    health_result = await db.execute(health_query)
    health_counts = {row[0].value: row[1] for row in health_result.all()}

    # Count by type
    type_query = select(
        DataConnector.connector_type, func.count(DataConnector.id)
    ).group_by(DataConnector.connector_type)
    type_result = await db.execute(type_query)
    type_counts = {row[0].value: row[1] for row in type_result.all()}

    # Total events
    events_query = select(
        func.sum(DataConnector.events_received),
        func.sum(DataConnector.events_processed),
        func.sum(DataConnector.events_failed),
        func.sum(DataConnector.bytes_received),
    )
    events_result = await db.execute(events_query)
    events_row = events_result.one()

    return {
        "total_connectors": sum(status_counts.values()),
        "by_status": status_counts,
        "by_health": health_counts,
        "by_type": type_counts,
        "total_events_received": events_row[0] or 0,
        "total_events_processed": events_row[1] or 0,
        "total_events_failed": events_row[2] or 0,
        "total_bytes_received": events_row[3] or 0,
    }
