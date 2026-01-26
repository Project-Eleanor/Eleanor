"""Playbook management API endpoints."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.tenant_context import get_current_tenant_id
from app.database import get_db
from app.models.playbook import (
    ApprovalStatus,
    ExecutionStatus,
    Playbook,
    PlaybookApproval,
    PlaybookExecution,
    PlaybookStatus,
    RulePlaybookBinding,
)
from app.services.playbook_engine import get_playbook_engine

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class StepConfig(BaseModel):
    """Configuration for a playbook step."""

    id: str
    name: str
    type: str  # action, condition, approval, delay, parallel, notification, soar
    action: str | None = None
    parameters: dict = Field(default_factory=dict)
    on_success: str | None = None
    on_failure: str | None = None
    on_approve: str | None = None
    on_deny: str | None = None
    timeout_seconds: int = 300
    conditions: list[dict] = Field(default_factory=list)
    approvers: list[str] = Field(default_factory=list)
    timeout_hours: int = 24


class PlaybookCreate(BaseModel):
    """Schema for creating a playbook."""

    name: str
    description: str | None = None
    steps: list[StepConfig] = Field(default_factory=list)
    trigger_on_alert: bool = False
    trigger_on_incident: bool = False
    trigger_conditions: dict = Field(default_factory=dict)
    input_schema: dict = Field(default_factory=dict)
    settings: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    category: str | None = None


class PlaybookUpdate(BaseModel):
    """Schema for updating a playbook."""

    name: str | None = None
    description: str | None = None
    status: PlaybookStatus | None = None
    steps: list[StepConfig] | None = None
    trigger_on_alert: bool | None = None
    trigger_on_incident: bool | None = None
    trigger_conditions: dict | None = None
    input_schema: dict | None = None
    settings: dict | None = None
    tags: list[str] | None = None
    category: str | None = None


class PlaybookResponse(BaseModel):
    """Schema for playbook response."""

    id: UUID
    name: str
    description: str | None
    version: int
    status: PlaybookStatus
    steps: list[dict]
    trigger_on_alert: bool
    trigger_on_incident: bool
    trigger_conditions: dict
    input_schema: dict
    settings: dict
    tags: list[str]
    category: str | None
    execution_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecutePlaybookRequest(BaseModel):
    """Request to execute a playbook."""

    input_data: dict = Field(default_factory=dict)
    trigger_type: str | None = None
    trigger_id: UUID | None = None


class ExecutionResponse(BaseModel):
    """Schema for execution response."""

    id: UUID
    playbook_id: UUID
    status: ExecutionStatus
    current_step_id: str | None
    trigger_type: str | None
    trigger_id: UUID | None
    input_data: dict
    output_data: dict
    step_results: list[dict]
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: int | None

    class Config:
        from_attributes = True


class ApprovalResponse(BaseModel):
    """Schema for approval response."""

    id: UUID
    execution_id: UUID
    step_id: str
    step_name: str
    status: ApprovalStatus
    context: dict
    required_approvers: list[str]
    created_at: datetime
    expires_at: datetime | None
    decided_at: datetime | None
    decision_comment: str | None

    class Config:
        from_attributes = True


class ApprovalDecision(BaseModel):
    """Schema for approval decision."""

    approved: bool
    comment: str | None = None


class BindPlaybookRequest(BaseModel):
    """Request to bind a playbook to a rule."""

    playbook_id: UUID
    enabled: bool = True
    priority: int = 0
    conditions: dict = Field(default_factory=dict)


class ActionDefinition(BaseModel):
    """Definition of an available action."""

    id: str
    name: str
    description: str
    parameters: dict


# =============================================================================
# Playbook CRUD
# =============================================================================


@router.post("", response_model=PlaybookResponse, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    playbook_data: PlaybookCreate,
    db: AsyncSession = Depends(get_db),
) -> Playbook:
    """Create a new playbook."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required"
        )

    playbook = Playbook(
        tenant_id=tenant_id,
        name=playbook_data.name,
        description=playbook_data.description,
        steps=[s.model_dump() for s in playbook_data.steps],
        trigger_on_alert=playbook_data.trigger_on_alert,
        trigger_on_incident=playbook_data.trigger_on_incident,
        trigger_conditions=playbook_data.trigger_conditions,
        input_schema=playbook_data.input_schema,
        settings=playbook_data.settings,
        tags=playbook_data.tags,
        category=playbook_data.category,
    )

    db.add(playbook)
    await db.flush()

    logger.info("Created playbook: %s (%s)", playbook.name, playbook.id)
    return playbook


@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(
    status_filter: PlaybookStatus | None = Query(None, alias="status"),
    category: str | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[Playbook]:
    """List playbooks."""
    tenant_id = get_current_tenant_id()
    query = select(Playbook)

    if tenant_id:
        query = query.where(Playbook.tenant_id == tenant_id)
    if status_filter:
        query = query.where(Playbook.status == status_filter)
    if category:
        query = query.where(Playbook.category == category)
    if search:
        query = query.where(Playbook.name.ilike(f"%{search}%"))

    query = query.order_by(Playbook.updated_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(
    playbook_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Playbook:
    """Get playbook details."""
    result = await db.execute(
        select(Playbook).where(Playbook.id == playbook_id)
    )
    playbook = result.scalar_one_or_none()

    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )

    return playbook


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    playbook_id: UUID,
    playbook_data: PlaybookUpdate,
    db: AsyncSession = Depends(get_db),
) -> Playbook:
    """Update a playbook."""
    result = await db.execute(
        select(Playbook).where(Playbook.id == playbook_id)
    )
    playbook = result.scalar_one_or_none()

    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )

    update_data = playbook_data.model_dump(exclude_unset=True)

    # Convert steps if provided
    if "steps" in update_data and update_data["steps"]:
        update_data["steps"] = [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in update_data["steps"]
        ]

    # Increment version if steps changed
    if "steps" in update_data:
        playbook.version += 1

    for field, value in update_data.items():
        setattr(playbook, field, value)

    logger.info("Updated playbook: %s", playbook.name)
    return playbook


@router.delete("/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playbook(
    playbook_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a playbook (archive it)."""
    result = await db.execute(
        select(Playbook).where(Playbook.id == playbook_id)
    )
    playbook = result.scalar_one_or_none()

    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )

    playbook.status = PlaybookStatus.ARCHIVED
    logger.info("Archived playbook: %s", playbook.name)


# =============================================================================
# Execution Endpoints
# =============================================================================


@router.post("/{playbook_id}/execute", response_model=ExecutionResponse)
async def execute_playbook(
    playbook_id: UUID,
    request: ExecutePlaybookRequest,
    db: AsyncSession = Depends(get_db),
) -> PlaybookExecution:
    """Execute a playbook."""
    engine = get_playbook_engine()

    try:
        execution = await engine.start_execution(
            playbook_id=playbook_id,
            input_data=request.input_data,
            trigger_type=request.trigger_type,
            trigger_id=request.trigger_id,
            started_by=None,  # TODO: Get from auth
            db=db,
        )

        # Execute asynchronously
        # In production, this would be a Celery task
        execution = await engine.execute(execution.id, db)

        return execution

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/executions", response_model=list[ExecutionResponse])
async def list_executions(
    playbook_id: UUID | None = None,
    status_filter: ExecutionStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[PlaybookExecution]:
    """List playbook executions."""
    tenant_id = get_current_tenant_id()
    query = select(PlaybookExecution)

    if tenant_id:
        query = query.where(PlaybookExecution.tenant_id == tenant_id)
    if playbook_id:
        query = query.where(PlaybookExecution.playbook_id == playbook_id)
    if status_filter:
        query = query.where(PlaybookExecution.status == status_filter)

    query = query.order_by(PlaybookExecution.started_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PlaybookExecution:
    """Get execution details."""
    result = await db.execute(
        select(PlaybookExecution)
        .options(joinedload(PlaybookExecution.playbook))
        .where(PlaybookExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )

    return execution


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PlaybookExecution:
    """Cancel a running execution."""
    engine = get_playbook_engine()

    try:
        execution = await engine.cancel_execution(
            execution_id=execution_id,
            cancelled_by=UUID("00000000-0000-0000-0000-000000000000"),  # TODO: Get from auth
            db=db,
        )
        return execution
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Approval Endpoints
# =============================================================================


@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    db: AsyncSession = Depends(get_db),
) -> list[PlaybookApproval]:
    """List pending approval requests."""
    tenant_id = get_current_tenant_id()
    query = select(PlaybookApproval).where(
        PlaybookApproval.status == ApprovalStatus.PENDING
    )

    if tenant_id:
        query = query.where(PlaybookApproval.tenant_id == tenant_id)

    query = query.order_by(PlaybookApproval.created_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/approvals/{approval_id}/approve", response_model=ExecutionResponse)
async def approve_step(
    approval_id: UUID,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
) -> PlaybookExecution:
    """Approve or deny a playbook step."""
    # Get approval
    result = await db.execute(
        select(PlaybookApproval).where(PlaybookApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found"
        )

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval already processed"
        )

    # Resume execution
    engine = get_playbook_engine()

    try:
        execution = await engine.resume_execution(
            execution_id=approval.execution_id,
            approved=decision.approved,
            decision_comment=decision.comment,
            decided_by=UUID("00000000-0000-0000-0000-000000000000"),  # TODO: Get from auth
            db=db,
        )
        return execution
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Rule Binding Endpoints
# =============================================================================


@router.post("/rules/{rule_id}/playbooks", status_code=status.HTTP_201_CREATED)
async def bind_playbook_to_rule(
    rule_id: UUID,
    request: BindPlaybookRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bind a playbook to a detection rule."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required"
        )

    # Verify playbook exists
    playbook_result = await db.execute(
        select(Playbook).where(Playbook.id == request.playbook_id)
    )
    if not playbook_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )

    # Check for existing binding
    existing = await db.execute(
        select(RulePlaybookBinding).where(
            RulePlaybookBinding.rule_id == rule_id,
            RulePlaybookBinding.playbook_id == request.playbook_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Binding already exists"
        )

    binding = RulePlaybookBinding(
        rule_id=rule_id,
        playbook_id=request.playbook_id,
        tenant_id=tenant_id,
        enabled=request.enabled,
        priority=request.priority,
        conditions=request.conditions,
    )

    db.add(binding)
    await db.flush()

    return {"id": str(binding.id), "message": "Playbook bound to rule"}


@router.get("/rules/{rule_id}/playbooks")
async def get_rule_playbooks(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get playbooks bound to a rule."""
    result = await db.execute(
        select(RulePlaybookBinding)
        .options(joinedload(RulePlaybookBinding.playbook))
        .where(RulePlaybookBinding.rule_id == rule_id)
        .order_by(RulePlaybookBinding.priority)
    )
    bindings = result.scalars().all()

    return [
        {
            "binding_id": str(b.id),
            "playbook_id": str(b.playbook_id),
            "playbook_name": b.playbook.name if b.playbook else None,
            "enabled": b.enabled,
            "priority": b.priority,
            "conditions": b.conditions,
        }
        for b in bindings
    ]


@router.delete("/rules/{rule_id}/playbooks/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_playbook_from_rule(
    rule_id: UUID,
    playbook_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a playbook binding from a rule."""
    result = await db.execute(
        select(RulePlaybookBinding).where(
            RulePlaybookBinding.rule_id == rule_id,
            RulePlaybookBinding.playbook_id == playbook_id,
        )
    )
    binding = result.scalar_one_or_none()

    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Binding not found"
        )

    await db.delete(binding)


# =============================================================================
# Actions Endpoint
# =============================================================================


@router.get("/actions", response_model=list[ActionDefinition])
async def list_available_actions() -> list[dict]:
    """List all available actions for playbook steps."""
    from app.services.action_executor import ActionExecutor

    return ActionExecutor.list_actions()
