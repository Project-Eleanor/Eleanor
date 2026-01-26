"""SOAR workflow endpoints.

Provides API endpoints for interacting with SOAR platforms like Shuffle
for workflow automation, approvals, and response action orchestration.

NOTE: Route ordering is important! Specific routes (/trigger, /executions,
/approvals, /actions/*) must be defined BEFORE the dynamic /{workflow_id}
route, otherwise FastAPI will match them as workflow_id values.
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


class WorkflowInfo(BaseModel):
    """Workflow information."""

    workflow_id: str
    name: str
    description: str | None = None
    category: str | None = None
    triggers: list[str] = []
    is_active: bool = True
    parameters: list[dict[str, Any]] = []
    created_at: str | None = None
    updated_at: str | None = None


class WorkflowTriggerRequest(BaseModel):
    """Request to trigger a workflow."""

    workflow_id: str = Field(..., description="ID of workflow to trigger")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for workflow",
    )


class WorkflowExecutionInfo(BaseModel):
    """Workflow execution information."""

    execution_id: str
    workflow_id: str
    workflow_name: str
    status: str  # pending, running, completed, failed, waiting_approval
    started_at: str | None = None
    completed_at: str | None = None
    triggered_by: str | None = None
    parameters: dict[str, Any] = {}
    results: dict[str, Any] = {}
    error: str | None = None


class ApprovalRequestInfo(BaseModel):
    """Pending approval request."""

    approval_id: str
    execution_id: str
    workflow_name: str
    action: str
    description: str
    requested_at: str
    requested_by: str | None = None
    expires_at: str | None = None
    parameters: dict[str, Any] = {}


class ApprovalDecision(BaseModel):
    """Approval decision request."""

    comment: str | None = Field(None, description="Optional comment")


class ResponseActionRequest(BaseModel):
    """Request for a common response action."""

    target: str = Field(..., description="Target hostname, IP, or username")
    case_id: str | None = Field(None, description="Associated case ID")
    reason: str | None = Field(None, description="Reason for action")


# =============================================================================
# Endpoints - Workflow Listing (root path)
# =============================================================================


@router.get("/", response_model=list[WorkflowInfo])
async def list_workflows(
    category: str | None = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only return active workflows"),
    current_user: User = Depends(get_current_user),
) -> list[WorkflowInfo]:
    """List available workflows."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    workflows = await soar_adapter.list_workflows(
        category=category,
        active_only=active_only,
    )

    return [
        WorkflowInfo(
            workflow_id=w.workflow_id,
            name=w.name,
            description=w.description,
            category=w.category,
            triggers=w.triggers,
            is_active=w.is_active,
            parameters=w.parameters,
            created_at=w.created_at.isoformat() if w.created_at else None,
            updated_at=w.updated_at.isoformat() if w.updated_at else None,
        )
        for w in workflows
    ]


# =============================================================================
# Endpoints - Trigger Workflow
# =============================================================================


@router.post("/trigger", response_model=WorkflowExecutionInfo)
async def trigger_workflow(
    request: WorkflowTriggerRequest,
    current_user: User = Depends(get_current_user),
) -> WorkflowExecutionInfo:
    """Trigger a workflow execution."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    execution = await soar_adapter.trigger_workflow(
        workflow_id=request.workflow_id,
        parameters=request.parameters,
        triggered_by=current_user.username if current_user else None,
    )

    return WorkflowExecutionInfo(
        execution_id=execution.execution_id,
        workflow_id=execution.workflow_id,
        workflow_name=execution.workflow_name,
        status=execution.status,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        triggered_by=execution.triggered_by,
        parameters=execution.parameters,
        results=execution.results,
        error=execution.error,
    )


# =============================================================================
# Endpoints - Execution Management
# =============================================================================


@router.get("/executions", response_model=list[WorkflowExecutionInfo])
async def list_executions(
    workflow_id: str | None = Query(None, description="Filter by workflow"),
    exec_status: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
) -> list[WorkflowExecutionInfo]:
    """List workflow executions."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    executions = await soar_adapter.list_executions(
        workflow_id=workflow_id,
        status=exec_status,
        limit=limit,
    )

    return [
        WorkflowExecutionInfo(
            execution_id=e.execution_id,
            workflow_id=e.workflow_id,
            workflow_name=e.workflow_name,
            status=e.status,
            started_at=e.started_at.isoformat() if e.started_at else None,
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
            triggered_by=e.triggered_by,
            parameters=e.parameters,
            results=e.results,
            error=e.error,
        )
        for e in executions
    ]


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionInfo)
async def get_execution_status(
    execution_id: str,
    current_user: User = Depends(get_current_user),
) -> WorkflowExecutionInfo:
    """Get status of a workflow execution."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    execution = await soar_adapter.get_execution_status(execution_id)

    return WorkflowExecutionInfo(
        execution_id=execution.execution_id,
        workflow_id=execution.workflow_id,
        workflow_name=execution.workflow_name,
        status=execution.status,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        triggered_by=execution.triggered_by,
        parameters=execution.parameters,
        results=execution.results,
        error=execution.error,
    )


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a running workflow execution."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    success = await soar_adapter.cancel_execution(execution_id)

    return {
        "success": success,
        "execution_id": execution_id,
        "message": "Execution cancelled" if success else "Failed to cancel execution",
    }


# =============================================================================
# Endpoints - Approval Management
# =============================================================================


@router.get("/approvals", response_model=list[ApprovalRequestInfo])
async def list_pending_approvals(
    current_user: User = Depends(get_current_user),
) -> list[ApprovalRequestInfo]:
    """List pending approval requests."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    approvals = await soar_adapter.list_pending_approvals()

    return [
        ApprovalRequestInfo(
            approval_id=a.approval_id,
            execution_id=a.execution_id,
            workflow_name=a.workflow_name,
            action=a.action,
            description=a.description,
            requested_at=a.requested_at.isoformat(),
            requested_by=a.requested_by,
            expires_at=a.expires_at.isoformat() if a.expires_at else None,
            parameters=a.parameters,
        )
        for a in approvals
    ]


@router.post("/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    decision: ApprovalDecision,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve an approval request."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    success = await soar_adapter.approve_request(
        approval_id=approval_id,
        approved_by=current_user.username if current_user else "unknown",
        comment=decision.comment,
    )

    return {
        "success": success,
        "approval_id": approval_id,
        "action": "approved",
        "message": "Request approved" if success else "Failed to approve request",
    }


@router.post("/approvals/{approval_id}/deny")
async def deny_request(
    approval_id: str,
    decision: ApprovalDecision,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Deny an approval request."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    success = await soar_adapter.deny_request(
        approval_id=approval_id,
        denied_by=current_user.username if current_user else "unknown",
        reason=decision.comment,
    )

    return {
        "success": success,
        "approval_id": approval_id,
        "action": "denied",
        "message": "Request denied" if success else "Failed to deny request",
    }


# =============================================================================
# Endpoints - Common Response Actions
# =============================================================================


@router.post("/actions/isolate-host", response_model=WorkflowExecutionInfo)
async def trigger_host_isolation(
    request: ResponseActionRequest,
    current_user: User = Depends(get_current_user),
) -> WorkflowExecutionInfo:
    """Trigger host isolation workflow.

    This will execute the configured host isolation workflow, which
    typically involves network isolation via EDR and firewall rules.
    """
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    execution = await soar_adapter.isolate_host_workflow(
        hostname=request.target,
        case_id=request.case_id,
    )

    return WorkflowExecutionInfo(
        execution_id=execution.execution_id,
        workflow_id=execution.workflow_id,
        workflow_name=execution.workflow_name,
        status=execution.status,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        triggered_by=current_user.username if current_user else None,
        parameters=execution.parameters,
    )


@router.post("/actions/block-ip", response_model=WorkflowExecutionInfo)
async def trigger_ip_block(
    request: ResponseActionRequest,
    current_user: User = Depends(get_current_user),
) -> WorkflowExecutionInfo:
    """Trigger IP blocking workflow.

    This will execute the configured IP blocking workflow, which
    typically involves firewall rule updates across the environment.
    """
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    execution = await soar_adapter.block_ip_workflow(
        ip_address=request.target,
        case_id=request.case_id,
    )

    return WorkflowExecutionInfo(
        execution_id=execution.execution_id,
        workflow_id=execution.workflow_id,
        workflow_name=execution.workflow_name,
        status=execution.status,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        triggered_by=current_user.username if current_user else None,
        parameters=execution.parameters,
    )


@router.post("/actions/disable-user", response_model=WorkflowExecutionInfo)
async def trigger_user_disable(
    request: ResponseActionRequest,
    current_user: User = Depends(get_current_user),
) -> WorkflowExecutionInfo:
    """Trigger user disable workflow.

    This will execute the configured user disable workflow, which
    typically involves Active Directory account disabling and session termination.
    """
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    execution = await soar_adapter.disable_user_workflow(
        username=request.target,
        case_id=request.case_id,
    )

    return WorkflowExecutionInfo(
        execution_id=execution.execution_id,
        workflow_id=execution.workflow_id,
        workflow_name=execution.workflow_name,
        status=execution.status,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        triggered_by=current_user.username if current_user else None,
        parameters=execution.parameters,
    )


# =============================================================================
# Endpoints - Get Workflow by ID (MUST BE LAST - catches all unmatched paths)
# =============================================================================


@router.get("/{workflow_id}", response_model=WorkflowInfo)
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
) -> WorkflowInfo:
    """Get details of a specific workflow."""
    registry = get_registry()
    soar_adapter = registry.get_soar()

    if not soar_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No SOAR adapter configured",
        )

    workflow = await soar_adapter.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    return WorkflowInfo(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        description=workflow.description,
        category=workflow.category,
        triggers=workflow.triggers,
        is_active=workflow.is_active,
        parameters=workflow.parameters,
        created_at=workflow.created_at.isoformat() if workflow.created_at else None,
        updated_at=workflow.updated_at.isoformat() if workflow.updated_at else None,
    )
