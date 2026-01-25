"""Analytics and detection rules API endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.analytics import (
    DetectionRule,
    RuleExecution,
    RuleSeverity,
    RuleStatus,
    RuleType,
)
from app.models.user import User

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class RuleCreate(BaseModel):
    """Create detection rule request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    rule_type: RuleType = RuleType.SCHEDULED
    severity: RuleSeverity = RuleSeverity.MEDIUM
    query: str = Field(..., min_length=1)
    query_language: str = "kql"
    indices: list[str] = []
    schedule_interval: int | None = Field(None, ge=1, le=1440)
    lookback_period: int | None = Field(None, ge=1, le=10080)
    threshold_count: int | None = Field(None, ge=1)
    threshold_field: str | None = None
    mitre_tactics: list[str] = []
    mitre_techniques: list[str] = []
    tags: list[str] = []
    category: str | None = None
    data_sources: list[str] = []
    auto_create_incident: bool = False
    playbook_id: str | None = None
    references: list[str] = []
    custom_fields: dict = {}


class RuleUpdate(BaseModel):
    """Update detection rule request."""

    name: str | None = None
    description: str | None = None
    rule_type: RuleType | None = None
    severity: RuleSeverity | None = None
    query: str | None = None
    query_language: str | None = None
    indices: list[str] | None = None
    schedule_interval: int | None = None
    lookback_period: int | None = None
    threshold_count: int | None = None
    threshold_field: str | None = None
    mitre_tactics: list[str] | None = None
    mitre_techniques: list[str] | None = None
    tags: list[str] | None = None
    category: str | None = None
    data_sources: list[str] | None = None
    auto_create_incident: bool | None = None
    playbook_id: str | None = None
    references: list[str] | None = None
    custom_fields: dict | None = None


class RuleResponse(BaseModel):
    """Detection rule response."""

    id: UUID
    name: str
    description: str | None
    rule_type: RuleType
    severity: RuleSeverity
    status: RuleStatus
    query: str
    query_language: str
    indices: list[str]
    schedule_interval: int | None
    lookback_period: int | None
    threshold_count: int | None
    threshold_field: str | None
    mitre_tactics: list[str]
    mitre_techniques: list[str]
    tags: list[str]
    category: str | None
    data_sources: list[str]
    auto_create_incident: bool
    playbook_id: str | None
    references: list[str]
    custom_fields: dict
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    hit_count: int
    false_positive_count: int

    class Config:
        from_attributes = True


class RuleListResponse(BaseModel):
    """Paginated rule list response."""

    items: list[RuleResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ExecutionResponse(BaseModel):
    """Rule execution response."""

    id: UUID
    rule_id: UUID
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    status: str
    hits_count: int
    events_scanned: int
    error_message: str | None
    incidents_created: int

    class Config:
        from_attributes = True


# =============================================================================
# Endpoints - Rule Management
# =============================================================================


@router.get("/rules", response_model=RuleListResponse)
async def list_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status_filter: RuleStatus | None = Query(None, alias="status"),
    severity: RuleSeverity | None = Query(None),
    rule_type: RuleType | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> RuleListResponse:
    """List detection rules with filtering and pagination."""
    query = select(DetectionRule)

    # Apply filters
    if status_filter:
        query = query.where(DetectionRule.status == status_filter)
    if severity:
        query = query.where(DetectionRule.severity == severity)
    if rule_type:
        query = query.where(DetectionRule.rule_type == rule_type)
    if category:
        query = query.where(DetectionRule.category == category)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (DetectionRule.name.ilike(search_filter))
            | (DetectionRule.description.ilike(search_filter))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(DetectionRule.name)

    result = await db.execute(query)
    rules = result.scalars().all()

    items = [
        RuleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            rule_type=r.rule_type,
            severity=r.severity,
            status=r.status,
            query=r.query,
            query_language=r.query_language,
            indices=r.indices,
            schedule_interval=r.schedule_interval,
            lookback_period=r.lookback_period,
            threshold_count=r.threshold_count,
            threshold_field=r.threshold_field,
            mitre_tactics=r.mitre_tactics,
            mitre_techniques=r.mitre_techniques,
            tags=r.tags,
            category=r.category,
            data_sources=r.data_sources,
            auto_create_incident=r.auto_create_incident,
            playbook_id=r.playbook_id,
            references=r.references,
            custom_fields=r.custom_fields,
            created_by=r.created_by,
            created_at=r.created_at,
            updated_at=r.updated_at,
            last_run_at=r.last_run_at,
            hit_count=r.hit_count,
            false_positive_count=r.false_positive_count,
        )
        for r in rules
    ]

    pages = (total + page_size - 1) // page_size if page_size else 1

    return RuleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RuleResponse:
    """Get detection rule by ID."""
    query = select(DetectionRule).where(DetectionRule.id == rule_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        severity=rule.severity,
        status=rule.status,
        query=rule.query,
        query_language=rule.query_language,
        indices=rule.indices,
        schedule_interval=rule.schedule_interval,
        lookback_period=rule.lookback_period,
        threshold_count=rule.threshold_count,
        threshold_field=rule.threshold_field,
        mitre_tactics=rule.mitre_tactics,
        mitre_techniques=rule.mitre_techniques,
        tags=rule.tags,
        category=rule.category,
        data_sources=rule.data_sources,
        auto_create_incident=rule.auto_create_incident,
        playbook_id=rule.playbook_id,
        references=rule.references,
        custom_fields=rule.custom_fields,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        last_run_at=rule.last_run_at,
        hit_count=rule.hit_count,
        false_positive_count=rule.false_positive_count,
    )


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: RuleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RuleResponse:
    """Create a new detection rule."""
    rule = DetectionRule(
        name=rule_data.name,
        description=rule_data.description,
        rule_type=rule_data.rule_type,
        severity=rule_data.severity,
        status=RuleStatus.DISABLED,
        query=rule_data.query,
        query_language=rule_data.query_language,
        indices=rule_data.indices,
        schedule_interval=rule_data.schedule_interval,
        lookback_period=rule_data.lookback_period,
        threshold_count=rule_data.threshold_count,
        threshold_field=rule_data.threshold_field,
        mitre_tactics=rule_data.mitre_tactics,
        mitre_techniques=rule_data.mitre_techniques,
        tags=rule_data.tags,
        category=rule_data.category,
        data_sources=rule_data.data_sources,
        auto_create_incident=rule_data.auto_create_incident,
        playbook_id=rule_data.playbook_id,
        references=rule_data.references,
        custom_fields=rule_data.custom_fields,
        created_by=current_user.id,
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        severity=rule.severity,
        status=rule.status,
        query=rule.query,
        query_language=rule.query_language,
        indices=rule.indices,
        schedule_interval=rule.schedule_interval,
        lookback_period=rule.lookback_period,
        threshold_count=rule.threshold_count,
        threshold_field=rule.threshold_field,
        mitre_tactics=rule.mitre_tactics,
        mitre_techniques=rule.mitre_techniques,
        tags=rule.tags,
        category=rule.category,
        data_sources=rule.data_sources,
        auto_create_incident=rule.auto_create_incident,
        playbook_id=rule.playbook_id,
        references=rule.references,
        custom_fields=rule.custom_fields,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        last_run_at=rule.last_run_at,
        hit_count=rule.hit_count,
        false_positive_count=rule.false_positive_count,
    )


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    updates: RuleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RuleResponse:
    """Update a detection rule."""
    query = select(DetectionRule).where(DetectionRule.id == rule_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        severity=rule.severity,
        status=rule.status,
        query=rule.query,
        query_language=rule.query_language,
        indices=rule.indices,
        schedule_interval=rule.schedule_interval,
        lookback_period=rule.lookback_period,
        threshold_count=rule.threshold_count,
        threshold_field=rule.threshold_field,
        mitre_tactics=rule.mitre_tactics,
        mitre_techniques=rule.mitre_techniques,
        tags=rule.tags,
        category=rule.category,
        data_sources=rule.data_sources,
        auto_create_incident=rule.auto_create_incident,
        playbook_id=rule.playbook_id,
        references=rule.references,
        custom_fields=rule.custom_fields,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        last_run_at=rule.last_run_at,
        hit_count=rule.hit_count,
        false_positive_count=rule.false_positive_count,
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a detection rule."""
    query = select(DetectionRule).where(DetectionRule.id == rule_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    await db.delete(rule)
    await db.commit()


@router.post("/rules/{rule_id}/enable", response_model=RuleResponse)
async def enable_rule(
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RuleResponse:
    """Enable a detection rule."""
    query = select(DetectionRule).where(DetectionRule.id == rule_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    rule.status = RuleStatus.ENABLED
    await db.commit()
    await db.refresh(rule)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        severity=rule.severity,
        status=rule.status,
        query=rule.query,
        query_language=rule.query_language,
        indices=rule.indices,
        schedule_interval=rule.schedule_interval,
        lookback_period=rule.lookback_period,
        threshold_count=rule.threshold_count,
        threshold_field=rule.threshold_field,
        mitre_tactics=rule.mitre_tactics,
        mitre_techniques=rule.mitre_techniques,
        tags=rule.tags,
        category=rule.category,
        data_sources=rule.data_sources,
        auto_create_incident=rule.auto_create_incident,
        playbook_id=rule.playbook_id,
        references=rule.references,
        custom_fields=rule.custom_fields,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        last_run_at=rule.last_run_at,
        hit_count=rule.hit_count,
        false_positive_count=rule.false_positive_count,
    )


@router.post("/rules/{rule_id}/disable", response_model=RuleResponse)
async def disable_rule(
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RuleResponse:
    """Disable a detection rule."""
    query = select(DetectionRule).where(DetectionRule.id == rule_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    rule.status = RuleStatus.DISABLED
    await db.commit()
    await db.refresh(rule)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        severity=rule.severity,
        status=rule.status,
        query=rule.query,
        query_language=rule.query_language,
        indices=rule.indices,
        schedule_interval=rule.schedule_interval,
        lookback_period=rule.lookback_period,
        threshold_count=rule.threshold_count,
        threshold_field=rule.threshold_field,
        mitre_tactics=rule.mitre_tactics,
        mitre_techniques=rule.mitre_techniques,
        tags=rule.tags,
        category=rule.category,
        data_sources=rule.data_sources,
        auto_create_incident=rule.auto_create_incident,
        playbook_id=rule.playbook_id,
        references=rule.references,
        custom_fields=rule.custom_fields,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        last_run_at=rule.last_run_at,
        hit_count=rule.hit_count,
        false_positive_count=rule.false_positive_count,
    )


# =============================================================================
# Endpoints - Rule Execution
# =============================================================================


@router.get("/rules/{rule_id}/executions", response_model=list[ExecutionResponse])
async def list_rule_executions(
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
) -> list[ExecutionResponse]:
    """List execution history for a rule."""
    query = (
        select(RuleExecution)
        .where(RuleExecution.rule_id == rule_id)
        .order_by(RuleExecution.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    executions = result.scalars().all()

    return [
        ExecutionResponse(
            id=e.id,
            rule_id=e.rule_id,
            started_at=e.started_at,
            completed_at=e.completed_at,
            duration_ms=e.duration_ms,
            status=e.status,
            hits_count=e.hits_count,
            events_scanned=e.events_scanned,
            error_message=e.error_message,
            incidents_created=e.incidents_created,
        )
        for e in executions
    ]


@router.post("/rules/{rule_id}/run", response_model=ExecutionResponse)
async def run_rule(
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ExecutionResponse:
    """Manually trigger a rule execution."""
    query = select(DetectionRule).where(DetectionRule.id == rule_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    # Create execution record
    execution = RuleExecution(
        rule_id=rule.id,
        status="running",
    )
    db.add(execution)

    # Update rule last_run_at
    rule.last_run_at = datetime.utcnow()

    await db.commit()
    await db.refresh(execution)

    # TODO: Actually run the rule query against Elasticsearch
    # This would be done asynchronously in a background task

    return ExecutionResponse(
        id=execution.id,
        rule_id=execution.rule_id,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=execution.duration_ms,
        status=execution.status,
        hits_count=execution.hits_count,
        events_scanned=execution.events_scanned,
        error_message=execution.error_message,
        incidents_created=execution.incidents_created,
    )


# =============================================================================
# Endpoints - Statistics
# =============================================================================


@router.get("/stats")
async def get_analytics_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get analytics statistics."""
    # Count rules by status
    status_query = select(
        DetectionRule.status, func.count(DetectionRule.id)
    ).group_by(DetectionRule.status)
    status_result = await db.execute(status_query)
    status_counts = {row[0].value: row[1] for row in status_result.all()}

    # Count rules by severity
    severity_query = select(
        DetectionRule.severity, func.count(DetectionRule.id)
    ).group_by(DetectionRule.severity)
    severity_result = await db.execute(severity_query)
    severity_counts = {row[0].value: row[1] for row in severity_result.all()}

    # Total hits
    hits_query = select(func.sum(DetectionRule.hit_count))
    hits_result = await db.execute(hits_query)
    total_hits = hits_result.scalar() or 0

    return {
        "total_rules": sum(status_counts.values()),
        "by_status": status_counts,
        "by_severity": severity_counts,
        "total_hits": total_hits,
    }
