"""Endpoint collection and response action endpoints.

Provides API endpoints for interacting with endpoint collection tools
like Velociraptor for artifact collection, hunts, and response actions.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.adapters import get_registry
from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class EndpointInfo(BaseModel):
    """Endpoint/client information."""

    client_id: str
    hostname: str
    os: str | None = None
    os_version: str | None = None
    ip_addresses: list[str] = []
    last_seen: str | None = None
    online: bool = False
    labels: dict[str, str] = {}


class ArtifactInfo(BaseModel):
    """Collection artifact definition."""

    name: str
    description: str | None = None
    category: str | None = None
    parameters: dict[str, Any] = {}


class CollectionRequest(BaseModel):
    """Request to collect an artifact."""

    client_id: str = Field(..., description="Target endpoint client ID")
    artifact_name: str = Field(..., description="Name of artifact to collect")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Artifact parameters",
    )
    urgent: bool = Field(
        default=False,
        description="Priority collection (faster but more resource intensive)",
    )


class CollectionJobInfo(BaseModel):
    """Collection job status."""

    job_id: str
    client_id: str
    artifact_name: str
    status: str  # pending, running, completed, failed
    started_at: str | None = None
    completed_at: str | None = None
    result_count: int = 0
    error: str | None = None


class HuntRequest(BaseModel):
    """Request to create a hunt."""

    name: str = Field(..., description="Hunt name")
    artifact_name: str = Field(..., description="Artifact to hunt with")
    description: str | None = Field(None, description="Hunt description")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Artifact parameters",
    )
    target_labels: dict[str, str] | None = Field(
        None,
        description="Label-based targeting",
    )
    expires_hours: int = Field(168, ge=1, le=720, description="Hours until hunt expires")


class HuntInfo(BaseModel):
    """Hunt information."""

    hunt_id: str
    name: str
    description: str | None = None
    artifact_name: str
    state: str  # paused, running, stopped, completed
    created_at: str | None = None
    started_at: str | None = None
    expires_at: str | None = None
    total_clients: int = 0
    completed_clients: int = 0


class ResponseActionRequest(BaseModel):
    """Request for a response action."""

    client_id: str = Field(..., description="Target endpoint client ID")
    reason: str | None = Field(None, description="Reason for action")


class ProcessKillRequest(BaseModel):
    """Request to kill a process."""

    client_id: str
    pid: int = Field(..., ge=1)
    reason: str | None = None


class FileQuarantineRequest(BaseModel):
    """Request to quarantine a file."""

    client_id: str
    file_path: str
    reason: str | None = None


# =============================================================================
# Endpoints - Endpoint Management
# =============================================================================


@router.get("/endpoints", response_model=list[EndpointInfo])
async def list_endpoints(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, description="Search by hostname or IP"),
    online_only: bool = Query(False, description="Only return online endpoints"),
    current_user: User = Depends(get_current_user),
) -> list[EndpointInfo]:
    """List managed endpoints."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    endpoints = await collection_adapter.list_endpoints(
        limit=limit,
        offset=offset,
        search=search,
        online_only=online_only,
    )

    return [
        EndpointInfo(
            client_id=e.client_id,
            hostname=e.hostname,
            os=e.os,
            os_version=e.os_version,
            ip_addresses=e.ip_addresses,
            last_seen=e.last_seen.isoformat() if e.last_seen else None,
            online=e.online,
            labels=e.labels,
        )
        for e in endpoints
    ]


@router.get("/endpoints/{client_id}", response_model=EndpointInfo)
async def get_endpoint(
    client_id: str,
    current_user: User = Depends(get_current_user),
) -> EndpointInfo:
    """Get details of a specific endpoint."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    endpoint = await collection_adapter.get_endpoint(client_id)
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint not found: {client_id}",
        )

    return EndpointInfo(
        client_id=endpoint.client_id,
        hostname=endpoint.hostname,
        os=endpoint.os,
        os_version=endpoint.os_version,
        ip_addresses=endpoint.ip_addresses,
        last_seen=endpoint.last_seen.isoformat() if endpoint.last_seen else None,
        online=endpoint.online,
        labels=endpoint.labels,
    )


@router.get("/endpoints/search/{query}", response_model=list[EndpointInfo])
async def search_endpoints(
    query: str,
    current_user: User = Depends(get_current_user),
) -> list[EndpointInfo]:
    """Search endpoints by hostname, IP, or label."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    endpoints = await collection_adapter.search_endpoints(query)

    return [
        EndpointInfo(
            client_id=e.client_id,
            hostname=e.hostname,
            os=e.os,
            os_version=e.os_version,
            ip_addresses=e.ip_addresses,
            last_seen=e.last_seen.isoformat() if e.last_seen else None,
            online=e.online,
            labels=e.labels,
        )
        for e in endpoints
    ]


# =============================================================================
# Endpoints - Artifact Collection
# =============================================================================


@router.get("/artifacts", response_model=list[ArtifactInfo])
async def list_artifacts(
    category: str | None = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
) -> list[ArtifactInfo]:
    """List available collection artifacts."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    artifacts = await collection_adapter.list_artifacts(category=category)

    return [
        ArtifactInfo(
            name=a.name,
            description=a.description,
            category=a.category,
            parameters=a.parameters,
        )
        for a in artifacts
    ]


@router.post("/collect", response_model=CollectionJobInfo)
async def collect_artifact(
    request: CollectionRequest,
    current_user: User = Depends(get_current_user),
) -> CollectionJobInfo:
    """Trigger artifact collection on an endpoint."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    job = await collection_adapter.collect_artifact(
        client_id=request.client_id,
        artifact_name=request.artifact_name,
        parameters=request.parameters,
        urgent=request.urgent,
    )

    return CollectionJobInfo(
        job_id=job.job_id,
        client_id=job.client_id,
        artifact_name=job.artifact_name,
        status=job.status,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        result_count=job.result_count,
        error=job.error,
    )


@router.get("/jobs/{job_id}", response_model=CollectionJobInfo)
async def get_collection_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> CollectionJobInfo:
    """Get status of a collection job."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    job = await collection_adapter.get_collection_status(job_id)

    return CollectionJobInfo(
        job_id=job.job_id,
        client_id=job.client_id,
        artifact_name=job.artifact_name,
        status=job.status,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        result_count=job.result_count,
        error=job.error,
    )


@router.get("/jobs/{job_id}/results")
async def get_collection_results(
    job_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get results from a completed collection job."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    return await collection_adapter.get_collection_results(job_id, limit)


# =============================================================================
# Endpoints - Hunt Management
# =============================================================================


@router.get("/hunts", response_model=list[HuntInfo])
async def list_hunts(
    limit: int = Query(50, ge=1, le=200),
    state: str | None = Query(None, description="Filter by state"),
    current_user: User = Depends(get_current_user),
) -> list[HuntInfo]:
    """List hunts."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    hunts = await collection_adapter.list_hunts(limit=limit, state=state)

    return [
        HuntInfo(
            hunt_id=h.hunt_id,
            name=h.name,
            description=h.description,
            artifact_name=h.artifact_name,
            state=h.state,
            created_at=h.created_at.isoformat() if h.created_at else None,
            started_at=h.started_at.isoformat() if h.started_at else None,
            expires_at=h.expires_at.isoformat() if h.expires_at else None,
            total_clients=h.total_clients,
            completed_clients=h.completed_clients,
        )
        for h in hunts
    ]


@router.post("/hunts", response_model=HuntInfo)
async def create_hunt(
    request: HuntRequest,
    current_user: User = Depends(get_current_user),
) -> HuntInfo:
    """Create a new hunt."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    hunt = await collection_adapter.create_hunt(
        name=request.name,
        artifact_name=request.artifact_name,
        description=request.description,
        parameters=request.parameters,
        target_labels=request.target_labels,
        expires_hours=request.expires_hours,
    )

    return HuntInfo(
        hunt_id=hunt.hunt_id,
        name=hunt.name,
        description=hunt.description,
        artifact_name=hunt.artifact_name,
        state=hunt.state,
        created_at=hunt.created_at.isoformat() if hunt.created_at else None,
        started_at=hunt.started_at.isoformat() if hunt.started_at else None,
        expires_at=hunt.expires_at.isoformat() if hunt.expires_at else None,
        total_clients=hunt.total_clients,
        completed_clients=hunt.completed_clients,
    )


@router.post("/hunts/{hunt_id}/start", response_model=HuntInfo)
async def start_hunt(
    hunt_id: str,
    current_user: User = Depends(get_current_user),
) -> HuntInfo:
    """Start a paused hunt."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    hunt = await collection_adapter.start_hunt(hunt_id)

    return HuntInfo(
        hunt_id=hunt.hunt_id,
        name=hunt.name,
        description=hunt.description,
        artifact_name=hunt.artifact_name,
        state=hunt.state,
        created_at=hunt.created_at.isoformat() if hunt.created_at else None,
        started_at=hunt.started_at.isoformat() if hunt.started_at else None,
        expires_at=hunt.expires_at.isoformat() if hunt.expires_at else None,
        total_clients=hunt.total_clients,
        completed_clients=hunt.completed_clients,
    )


@router.post("/hunts/{hunt_id}/stop", response_model=HuntInfo)
async def stop_hunt(
    hunt_id: str,
    current_user: User = Depends(get_current_user),
) -> HuntInfo:
    """Stop a running hunt."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    hunt = await collection_adapter.stop_hunt(hunt_id)

    return HuntInfo(
        hunt_id=hunt.hunt_id,
        name=hunt.name,
        description=hunt.description,
        artifact_name=hunt.artifact_name,
        state=hunt.state,
        created_at=hunt.created_at.isoformat() if hunt.created_at else None,
        started_at=hunt.started_at.isoformat() if hunt.started_at else None,
        expires_at=hunt.expires_at.isoformat() if hunt.expires_at else None,
        total_clients=hunt.total_clients,
        completed_clients=hunt.completed_clients,
    )


@router.get("/hunts/{hunt_id}/results")
async def get_hunt_results(
    hunt_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get aggregated results from a hunt."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    return await collection_adapter.get_hunt_results(hunt_id, limit)


# =============================================================================
# Endpoints - Response Actions
# =============================================================================


@router.post("/response/isolate")
async def isolate_host(
    request: ResponseActionRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Isolate a host from the network.

    This is a high-impact action that should be used carefully.
    """
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    success = await collection_adapter.isolate_host(request.client_id)

    return {
        "success": success,
        "client_id": request.client_id,
        "action": "isolate",
        "message": "Host isolation initiated" if success else "Isolation failed",
    }


@router.post("/response/unisolate")
async def unisolate_host(
    request: ResponseActionRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Remove network isolation from a host."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    success = await collection_adapter.unisolate_host(request.client_id)

    return {
        "success": success,
        "client_id": request.client_id,
        "action": "unisolate",
        "message": "Host unisolation initiated" if success else "Unisolation failed",
    }


@router.post("/response/quarantine-file")
async def quarantine_file(
    request: FileQuarantineRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Quarantine a file on an endpoint."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    success = await collection_adapter.quarantine_file(
        request.client_id,
        request.file_path,
    )

    return {
        "success": success,
        "client_id": request.client_id,
        "file_path": request.file_path,
        "action": "quarantine",
        "message": "File quarantine initiated" if success else "Quarantine failed",
    }


@router.post("/response/kill-process")
async def kill_process(
    request: ProcessKillRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Kill a process on an endpoint."""
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    success = await collection_adapter.kill_process(
        request.client_id,
        request.pid,
    )

    return {
        "success": success,
        "client_id": request.client_id,
        "pid": request.pid,
        "action": "kill_process",
        "message": "Process kill initiated" if success else "Kill failed",
    }
