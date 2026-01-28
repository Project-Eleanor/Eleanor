"""Response action API endpoints.

Provides endpoints for host isolation, file quarantine, process termination,
and other incident response actions with comprehensive audit logging.
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import get_registry
from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.response_action import ResponseAction, ResponseActionStatus, ResponseActionType
from app.models.user import User
from app.services.audit import AuditService, ResponseActionService

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class IsolateRequest(BaseModel):
    """Request to isolate a host."""

    client_id: str = Field(..., description="Target endpoint client ID")
    reason: str = Field(..., min_length=10, description="Reason for isolation (required for audit)")
    case_id: Optional[UUID] = Field(None, description="Associated case ID")
    hostname: Optional[str] = Field(None, description="Target hostname for reference")


class ReleaseRequest(BaseModel):
    """Request to release a host from isolation."""

    client_id: str = Field(..., description="Target endpoint client ID")
    reason: str = Field(..., min_length=10, description="Reason for release (required for audit)")
    case_id: Optional[UUID] = Field(None, description="Associated case ID")


class QuarantineFileRequest(BaseModel):
    """Request to quarantine a file."""

    client_id: str = Field(..., description="Target endpoint client ID")
    file_path: str = Field(..., description="Full path to file to quarantine")
    reason: str = Field(..., min_length=10, description="Reason for quarantine")
    case_id: Optional[UUID] = Field(None, description="Associated case ID")


class KillProcessRequest(BaseModel):
    """Request to kill a process."""

    client_id: str = Field(..., description="Target endpoint client ID")
    pid: int = Field(..., ge=1, description="Process ID to terminate")
    reason: str = Field(..., min_length=10, description="Reason for termination")
    case_id: Optional[UUID] = Field(None, description="Associated case ID")


class ResponseActionInfo(BaseModel):
    """Response action information."""

    id: UUID
    action_type: str
    status: str
    client_id: str
    hostname: Optional[str] = None
    target_details: dict[str, Any] = {}
    reason: Optional[str] = None
    job_id: Optional[str] = None
    case_id: Optional[UUID] = None
    user_id: UUID
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class IsolationStatus(BaseModel):
    """Host isolation status."""

    client_id: str
    is_isolated: bool
    last_action: Optional[str] = None
    last_action_at: Optional[str] = None
    last_action_by: Optional[str] = None


class ResponseActionResult(BaseModel):
    """Result of a response action."""

    success: bool
    action_id: UUID
    client_id: str
    action_type: str
    message: str
    job_id: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    """Dependency for audit service."""
    return AuditService(db)


async def get_response_service(
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> ResponseActionService:
    """Dependency for response action service."""
    return ResponseActionService(db, audit)


# PATTERN: DTO Mapping Helper
# Centralizes the conversion from ResponseAction domain model to ResponseActionInfo DTO.
# This eliminates repeated field mapping code across multiple endpoints.
def _to_response_action_info(action: ResponseAction) -> ResponseActionInfo:
    """Convert a ResponseAction model to a ResponseActionInfo DTO.

    Args:
        action: The ResponseAction domain model instance

    Returns:
        ResponseActionInfo DTO with all fields mapped from the domain model
    """
    return ResponseActionInfo(
        id=action.id,
        action_type=action.action_type,
        status=action.status,
        client_id=action.client_id,
        hostname=action.hostname,
        target_details=action.target_details,
        reason=action.reason,
        job_id=action.job_id,
        case_id=action.case_id,
        user_id=action.user_id,
        created_at=action.created_at,
        started_at=action.started_at,
        completed_at=action.completed_at,
        error_message=action.error_message,
    )


# =============================================================================
# Endpoints - Host Isolation
# =============================================================================


@router.post("/isolate", response_model=ResponseActionResult)
async def isolate_host(
    request_body: IsolateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    response_service: ResponseActionService = Depends(get_response_service),
) -> ResponseActionResult:
    """Isolate a host from the network.

    This is a high-impact action that disconnects the endpoint from all
    network communication except to the management server. Use with caution.

    Requires audit trail with mandatory reason documentation.
    """
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    # Create response action record
    action = await response_service.create_action(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action_type=ResponseActionType.ISOLATE,
        client_id=request_body.client_id,
        hostname=request_body.hostname,
        case_id=request_body.case_id,
        reason=request_body.reason,
    )

    # Log to audit
    await audit.log_response_action(
        action_type=ResponseActionType.ISOLATE,
        user_id=current_user.id,
        username=current_user.username,
        client_id=request_body.client_id,
        hostname=request_body.hostname,
        case_id=request_body.case_id,
        reason=request_body.reason,
        ip_address=get_client_ip(request),
    )

    # Update status to in_progress
    await response_service.update_action_status(
        action_id=action.id,
        status=ResponseActionStatus.IN_PROGRESS,
    )

    # Execute isolation
    try:
        success = await collection_adapter.isolate_host(request_body.client_id)

        if success:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.COMPLETED,
                result={"isolated": True},
            )
            return ResponseActionResult(
                success=True,
                action_id=action.id,
                client_id=request_body.client_id,
                action_type="isolate",
                message="Host isolation initiated successfully",
            )
        else:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.FAILED,
                error_message="Isolation command failed",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Host isolation failed",
            )
    except HTTPException:
        raise
    except Exception as e:
        await response_service.update_action_status(
            action_id=action.id,
            status=ResponseActionStatus.FAILED,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Host isolation error: {e}",
        )


@router.post("/release", response_model=ResponseActionResult)
async def release_host(
    request_body: ReleaseRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    response_service: ResponseActionService = Depends(get_response_service),
) -> ResponseActionResult:
    """Remove network isolation from a host.

    Restores full network connectivity to a previously isolated endpoint.
    """
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    # Create response action record
    action = await response_service.create_action(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action_type=ResponseActionType.RELEASE,
        client_id=request_body.client_id,
        case_id=request_body.case_id,
        reason=request_body.reason,
    )

    # Log to audit
    await audit.log_response_action(
        action_type=ResponseActionType.RELEASE,
        user_id=current_user.id,
        username=current_user.username,
        client_id=request_body.client_id,
        case_id=request_body.case_id,
        reason=request_body.reason,
        ip_address=get_client_ip(request),
    )

    # Update status to in_progress
    await response_service.update_action_status(
        action_id=action.id,
        status=ResponseActionStatus.IN_PROGRESS,
    )

    # Execute release
    try:
        success = await collection_adapter.unisolate_host(request_body.client_id)

        if success:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.COMPLETED,
                result={"released": True},
            )
            return ResponseActionResult(
                success=True,
                action_id=action.id,
                client_id=request_body.client_id,
                action_type="release",
                message="Host release initiated successfully",
            )
        else:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.FAILED,
                error_message="Release command failed",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Host release failed",
            )
    except HTTPException:
        raise
    except Exception as e:
        await response_service.update_action_status(
            action_id=action.id,
            status=ResponseActionStatus.FAILED,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Host release error: {e}",
        )


@router.get("/status/{client_id}", response_model=IsolationStatus)
async def get_isolation_status(
    client_id: str,
    current_user: User = Depends(get_current_user),
    response_service: ResponseActionService = Depends(get_response_service),
) -> IsolationStatus:
    """Get current isolation status for a host."""
    status_info = await response_service.get_isolation_status(
        client_id=client_id,
        tenant_id=current_user.tenant_id,
    )

    return IsolationStatus(
        client_id=client_id,
        **status_info,
    )


# =============================================================================
# Endpoints - File Quarantine
# =============================================================================


@router.post("/quarantine-file", response_model=ResponseActionResult)
async def quarantine_file(
    request_body: QuarantineFileRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    response_service: ResponseActionService = Depends(get_response_service),
) -> ResponseActionResult:
    """Quarantine a file on an endpoint.

    Moves the specified file to a secure quarantine location on the endpoint,
    preventing execution while preserving the file for analysis.
    """
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    # Create response action record
    action = await response_service.create_action(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action_type=ResponseActionType.QUARANTINE_FILE,
        client_id=request_body.client_id,
        case_id=request_body.case_id,
        reason=request_body.reason,
        target_details={"file_path": request_body.file_path},
    )

    # Log to audit
    await audit.log_response_action(
        action_type=ResponseActionType.QUARANTINE_FILE,
        user_id=current_user.id,
        username=current_user.username,
        client_id=request_body.client_id,
        case_id=request_body.case_id,
        reason=request_body.reason,
        target_details={"file_path": request_body.file_path},
        ip_address=get_client_ip(request),
    )

    # Update status to in_progress
    await response_service.update_action_status(
        action_id=action.id,
        status=ResponseActionStatus.IN_PROGRESS,
    )

    # Execute quarantine
    try:
        success = await collection_adapter.quarantine_file(
            request_body.client_id,
            request_body.file_path,
        )

        if success:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.COMPLETED,
                result={"quarantined": True, "file_path": request_body.file_path},
            )
            return ResponseActionResult(
                success=True,
                action_id=action.id,
                client_id=request_body.client_id,
                action_type="quarantine_file",
                message=f"File quarantine initiated for: {request_body.file_path}",
            )
        else:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.FAILED,
                error_message="Quarantine command failed",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File quarantine failed",
            )
    except HTTPException:
        raise
    except Exception as e:
        await response_service.update_action_status(
            action_id=action.id,
            status=ResponseActionStatus.FAILED,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File quarantine error: {e}",
        )


# =============================================================================
# Endpoints - Process Termination
# =============================================================================


@router.post("/kill-process", response_model=ResponseActionResult)
async def kill_process(
    request_body: KillProcessRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    response_service: ResponseActionService = Depends(get_response_service),
) -> ResponseActionResult:
    """Kill a process on an endpoint.

    Terminates the specified process by PID on the target endpoint.
    """
    registry = get_registry()
    collection_adapter = registry.get_collection()

    if not collection_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No collection adapter configured",
        )

    # Create response action record
    action = await response_service.create_action(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action_type=ResponseActionType.KILL_PROCESS,
        client_id=request_body.client_id,
        case_id=request_body.case_id,
        reason=request_body.reason,
        target_details={"pid": request_body.pid},
    )

    # Log to audit
    await audit.log_response_action(
        action_type=ResponseActionType.KILL_PROCESS,
        user_id=current_user.id,
        username=current_user.username,
        client_id=request_body.client_id,
        case_id=request_body.case_id,
        reason=request_body.reason,
        target_details={"pid": request_body.pid},
        ip_address=get_client_ip(request),
    )

    # Update status to in_progress
    await response_service.update_action_status(
        action_id=action.id,
        status=ResponseActionStatus.IN_PROGRESS,
    )

    # Execute kill
    try:
        success = await collection_adapter.kill_process(
            request_body.client_id,
            request_body.pid,
        )

        if success:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.COMPLETED,
                result={"killed": True, "pid": request_body.pid},
            )
            return ResponseActionResult(
                success=True,
                action_id=action.id,
                client_id=request_body.client_id,
                action_type="kill_process",
                message=f"Process termination initiated for PID: {request_body.pid}",
            )
        else:
            await response_service.update_action_status(
                action_id=action.id,
                status=ResponseActionStatus.FAILED,
                error_message="Kill command failed",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Process termination failed",
            )
    except HTTPException:
        raise
    except Exception as e:
        await response_service.update_action_status(
            action_id=action.id,
            status=ResponseActionStatus.FAILED,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Process termination error: {e}",
        )


# =============================================================================
# Endpoints - Action History
# =============================================================================


@router.get("/actions", response_model=list[ResponseActionInfo])
async def list_response_actions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    current_user: User = Depends(get_current_user),
    response_service: ResponseActionService = Depends(get_response_service),
) -> list[ResponseActionInfo]:
    """List response action history.

    Returns a paginated list of response actions with optional filters.
    """
    # Parse action type filter
    action_type_enum = None
    if action_type:
        try:
            action_type_enum = ResponseActionType(action_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action type: {action_type}",
            )

    # Parse status filter
    status_enum = None
    if status_filter:
        try:
            status_enum = ResponseActionStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    actions = await response_service.get_action_history(
        tenant_id=current_user.tenant_id,
        limit=limit,
        offset=offset,
        action_type=action_type_enum,
        status=status_enum,
        client_id=client_id,
    )

    return [_to_response_action_info(action) for action in actions]


@router.get("/actions/{action_id}", response_model=ResponseActionInfo)
async def get_response_action(
    action_id: UUID,
    current_user: User = Depends(get_current_user),
    response_service: ResponseActionService = Depends(get_response_service),
) -> ResponseActionInfo:
    """Get details of a specific response action."""
    action = await response_service.get_action(action_id)

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response action not found",
        )

    # Verify tenant access
    if action.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this response action",
        )

    return _to_response_action_info(action)


@router.get("/actions/client/{client_id}", response_model=list[ResponseActionInfo])
async def get_client_actions(
    client_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    response_service: ResponseActionService = Depends(get_response_service),
) -> list[ResponseActionInfo]:
    """Get response actions for a specific client/endpoint."""
    actions = await response_service.get_actions_by_client(
        client_id=client_id,
        tenant_id=current_user.tenant_id,
        limit=limit,
    )

    return [_to_response_action_info(action) for action in actions]


@router.get("/actions/case/{case_id}", response_model=list[ResponseActionInfo])
async def get_case_actions(
    case_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    response_service: ResponseActionService = Depends(get_response_service),
) -> list[ResponseActionInfo]:
    """Get response actions linked to a specific case."""
    actions = await response_service.get_actions_by_case(
        case_id=case_id,
        limit=limit,
    )

    # Filter by tenant
    tenant_actions = [action for action in actions if action.tenant_id == current_user.tenant_id]

    return [_to_response_action_info(action) for action in tenant_actions]
