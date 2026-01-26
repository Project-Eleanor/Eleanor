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
from app.services.detection_engine import get_detection_engine
from app.services.alert_generator import get_alert_generator
from app.services.correlation_engine import get_correlation_engine
from app.services.event_buffer import get_event_buffer, EVENT_STREAM
from app.services.realtime_processor import get_realtime_processor

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class CorrelationConfig(BaseModel):
    """Correlation rule configuration."""

    pattern_type: str = Field(
        ...,
        description="Pattern type: sequence, temporal_join, aggregation, spike",
    )
    window: str = Field("5m", description="Time window (e.g., '5m', '1h')")
    events: list[dict] = Field(
        default=[],
        description="Event definitions with id and query",
    )
    join_on: list[dict] = Field(
        default=[],
        description="Fields to join events on",
    )
    sequence: dict | None = Field(
        default=None,
        description="Sequence order configuration",
    )
    thresholds: list[dict] = Field(
        default=[],
        description="Threshold conditions per event",
    )
    group_by: list[str] = Field(
        default=[],
        description="Fields to group aggregations by",
    )
    query: str | None = Field(
        default=None,
        description="Base query for aggregation/spike patterns",
    )
    threshold: dict | None = Field(
        default=None,
        description="Threshold for aggregation pattern",
    )
    baseline_window: str | None = Field(
        default=None,
        description="Baseline window for spike detection",
    )
    current_window: str | None = Field(
        default=None,
        description="Current window for spike detection",
    )
    spike_factor: float | None = Field(
        default=None,
        description="Spike factor threshold",
    )
    realtime: bool = Field(
        default=False,
        description="Enable real-time processing",
    )
    lookback: str | None = Field(
        default=None,
        description="Lookback period for temporal join",
    )


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
    correlation_config: CorrelationConfig | None = None


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
    correlation_config: CorrelationConfig | None = None


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
    correlation_config: dict | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    hit_count: int | None = 0
    false_positive_count: int | None = 0

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
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    status: str
    hits_count: int | None = 0
    events_scanned: int | None = 0
    error_message: str | None = None
    incidents_created: int | None = 0

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
            correlation_config=r.correlation_config,
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
        correlation_config=rule.correlation_config,
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
        correlation_config=rule_data.correlation_config.model_dump() if rule_data.correlation_config else None,
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
        correlation_config=rule.correlation_config,
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
            # Handle correlation_config specially to convert from Pydantic model
            if field == "correlation_config" and isinstance(value, dict):
                setattr(rule, field, value)
            else:
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
        correlation_config=rule.correlation_config,
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
        correlation_config=rule.correlation_config,
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
        correlation_config=rule.correlation_config,
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
    await db.flush()

    # Execute the rule using the detection engine
    detection_engine = await get_detection_engine()
    exec_result = await detection_engine.execute_rule(rule, execution, db)

    # If threshold exceeded, create alerts
    if exec_result.get("threshold_exceeded") and exec_result.get("hits"):
        alert_generator = get_alert_generator()
        alerts = await alert_generator.create_alerts_from_rule_execution(
            rule, exec_result, db
        )
        execution.incidents_created = len(alerts)
        await db.commit()

    # Refresh to get updated values
    await db.refresh(execution)

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


# =============================================================================
# Endpoints - Correlation Rules
# =============================================================================


class CorrelationExecuteResponse(BaseModel):
    """Correlation rule execution response."""

    rule_id: str
    execution_id: str
    pattern_type: str
    matches: list[dict]
    hits_count: int
    duration_ms: int
    status: str
    error: str | None = None


@router.post("/rules/{rule_id}/run-correlation", response_model=CorrelationExecuteResponse)
async def run_correlation_rule(
    rule_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CorrelationExecuteResponse:
    """Execute a correlation rule manually."""
    query = select(DetectionRule).where(DetectionRule.id == rule_id)
    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    if rule.rule_type != RuleType.CORRELATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule is not a correlation rule",
        )

    if not rule.correlation_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule has no correlation configuration",
        )

    # Create execution record
    execution = RuleExecution(
        rule_id=rule.id,
        status="running",
    )
    db.add(execution)
    await db.flush()

    # Execute the correlation rule
    correlation_engine = await get_correlation_engine()
    exec_result = await correlation_engine.execute_correlation_rule(
        rule, execution, db
    )

    return CorrelationExecuteResponse(
        rule_id=exec_result["rule_id"],
        execution_id=exec_result["execution_id"],
        pattern_type=exec_result.get("pattern_type", "unknown"),
        matches=exec_result.get("matches", []),
        hits_count=exec_result.get("hits_count", 0),
        duration_ms=exec_result.get("duration_ms", 0),
        status=exec_result.get("status", "unknown"),
        error=exec_result.get("error"),
    )


class CorrelationTestRequest(BaseModel):
    """Request to test a correlation configuration."""

    config: CorrelationConfig
    lookback_minutes: int = Field(60, ge=1, le=1440)


class CorrelationTestResponse(BaseModel):
    """Response from testing a correlation configuration."""

    pattern_type: str
    matches: list[dict]
    match_count: int
    events_analyzed: int
    duration_ms: int


@router.post("/correlation/test", response_model=CorrelationTestResponse)
async def test_correlation_config(
    request: CorrelationTestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CorrelationTestResponse:
    """Test a correlation configuration without creating a rule."""
    from datetime import timedelta
    from uuid import uuid4

    # Create a temporary rule object
    temp_rule = DetectionRule(
        id=uuid4(),
        name="__test_correlation__",
        query="*",
        rule_type=RuleType.CORRELATION,
        correlation_config=request.config.model_dump(),
    )

    # Create temporary execution
    temp_execution = RuleExecution(
        rule_id=temp_rule.id,
        status="running",
    )

    correlation_engine = await get_correlation_engine()

    start_time = datetime.utcnow()
    try:
        result = await correlation_engine.execute_correlation_rule(
            temp_rule, temp_execution, db
        )
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return CorrelationTestResponse(
            pattern_type=request.config.pattern_type,
            matches=result.get("matches", []),
            match_count=len(result.get("matches", [])),
            events_analyzed=0,  # Would need to track this in engine
            duration_ms=duration_ms,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Correlation test failed: {str(e)}",
        )


# =============================================================================
# Endpoints - Real-Time Processing
# =============================================================================


class RealtimeProcessorStatus(BaseModel):
    """Real-time processor status response."""

    running: bool
    uptime_seconds: float | None
    events_processed: int
    alerts_generated: int
    correlations_matched: int
    errors: int
    active_workers: int


@router.get("/realtime/status", response_model=RealtimeProcessorStatus)
async def get_realtime_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> RealtimeProcessorStatus:
    """Get real-time processor status."""
    try:
        processor = await get_realtime_processor()
        stats = processor.get_stats()

        return RealtimeProcessorStatus(
            running=stats["running"],
            uptime_seconds=stats.get("uptime_seconds"),
            events_processed=stats["events_processed"],
            alerts_generated=stats["alerts_generated"],
            correlations_matched=stats["correlations_matched"],
            errors=stats["errors"],
            active_workers=stats["active_workers"],
        )
    except Exception as e:
        return RealtimeProcessorStatus(
            running=False,
            uptime_seconds=None,
            events_processed=0,
            alerts_generated=0,
            correlations_matched=0,
            errors=0,
            active_workers=0,
        )


class EventStreamStatus(BaseModel):
    """Event stream status response."""

    stream: str
    length: int
    first_entry: dict | None
    last_entry: dict | None
    groups: list[dict]
    error: str | None = None


@router.get("/realtime/streams", response_model=list[EventStreamStatus])
async def get_stream_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[EventStreamStatus]:
    """Get status of event streams."""
    from app.services.event_buffer import (
        EVENT_STREAM,
        ALERT_STREAM,
        CORRELATION_STREAM,
        DEAD_LETTER_STREAM,
    )

    try:
        event_buffer = await get_event_buffer()

        streams = []
        for stream_name in [EVENT_STREAM, ALERT_STREAM, CORRELATION_STREAM, DEAD_LETTER_STREAM]:
            info = await event_buffer.get_stream_info(stream_name)
            streams.append(EventStreamStatus(
                stream=info["stream"],
                length=info.get("length", 0),
                first_entry=info.get("first_entry"),
                last_entry=info.get("last_entry"),
                groups=info.get("groups", []),
                error=info.get("error"),
            ))

        return streams
    except Exception as e:
        return [EventStreamStatus(
            stream="error",
            length=0,
            first_entry=None,
            last_entry=None,
            groups=[],
            error=str(e),
        )]


# =============================================================================
# Endpoints - Correlation Templates
# =============================================================================


CORRELATION_TEMPLATES = [
    {
        "name": "Brute Force Attack",
        "description": "Detects multiple failed login attempts followed by a successful login",
        "pattern_type": "sequence",
        "config": {
            "pattern_type": "sequence",
            "window": "5m",
            "events": [
                {"id": "failed_logins", "query": "event.action:logon_failed"},
                {"id": "success", "query": "event.action:logon AND event.outcome:success"},
            ],
            "join_on": [{"field": "user.name"}],
            "sequence": {"order": ["failed_logins", "success"]},
            "thresholds": [{"event": "failed_logins", "count": ">= 5"}],
            "realtime": True,
        },
    },
    {
        "name": "Lateral Movement",
        "description": "Detects authentication from one host followed by RDP/SMB to another",
        "pattern_type": "temporal_join",
        "config": {
            "pattern_type": "temporal_join",
            "window": "10m",
            "lookback": "1h",
            "events": [
                {"id": "local_auth", "query": "event.action:logon AND event.type:start"},
                {"id": "remote_conn", "query": "destination.port:(3389 OR 445)"},
            ],
            "join_on": [{"field": "user.name"}],
            "realtime": False,
        },
    },
    {
        "name": "Anomalous Process Execution",
        "description": "Detects unusual spike in process creation for a host",
        "pattern_type": "spike",
        "config": {
            "pattern_type": "spike",
            "current_window": "5m",
            "baseline_window": "1h",
            "spike_factor": 3.0,
            "query": "event.category:process AND event.type:start",
            "group_by": ["host.name"],
            "realtime": False,
        },
    },
    {
        "name": "Data Exfiltration Indicator",
        "description": "Detects unusually high outbound data transfer per host",
        "pattern_type": "aggregation",
        "config": {
            "pattern_type": "aggregation",
            "window": "15m",
            "query": "network.direction:outbound",
            "group_by": ["host.name", "destination.ip"],
            "threshold": {"count": ">= 1000"},
            "realtime": False,
        },
    },
]


class CorrelationTemplate(BaseModel):
    """Correlation rule template."""

    name: str
    description: str
    pattern_type: str
    config: dict


@router.get("/correlation/templates", response_model=list[CorrelationTemplate])
async def list_correlation_templates(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CorrelationTemplate]:
    """List available correlation rule templates."""
    return [
        CorrelationTemplate(
            name=t["name"],
            description=t["description"],
            pattern_type=t["pattern_type"],
            config=t["config"],
        )
        for t in CORRELATION_TEMPLATES
    ]


@router.post("/correlation/templates/{template_name}/create", response_model=RuleResponse)
async def create_rule_from_template(
    template_name: str,
    name: str = Query(..., min_length=1, max_length=255),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> RuleResponse:
    """Create a correlation rule from a template."""
    # Find template
    template = next(
        (t for t in CORRELATION_TEMPLATES if t["name"] == template_name),
        None,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found",
        )

    # Create rule
    rule = DetectionRule(
        name=name,
        description=template["description"],
        rule_type=RuleType.CORRELATION,
        severity=RuleSeverity.MEDIUM,
        query="*",  # Correlation rules use config instead
        correlation_config=template["config"],
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
        correlation_config=rule.correlation_config,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        last_run_at=rule.last_run_at,
        hit_count=rule.hit_count,
        false_positive_count=rule.false_positive_count,
    )
