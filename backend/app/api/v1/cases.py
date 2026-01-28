"""Cases API endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.case import Case, CaseStatus, Priority, Severity
from app.models.user import User

router = APIRouter()
settings = get_settings()


class CaseCreate(BaseModel):
    """Case creation request."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    severity: Severity = Severity.MEDIUM
    priority: Priority = Priority.P3
    assignee_id: UUID | None = None
    tags: list[str] = []
    mitre_tactics: list[str] = []
    mitre_techniques: list[str] = []
    metadata: dict = {}


class CaseUpdate(BaseModel):
    """Case update request."""

    title: str | None = None
    description: str | None = None
    severity: Severity | None = None
    priority: Priority | None = None
    status: CaseStatus | None = None
    assignee_id: UUID | None = None
    tags: list[str] | None = None
    mitre_tactics: list[str] | None = None
    mitre_techniques: list[str] | None = None
    metadata: dict | None = None


class CaseResponse(BaseModel):
    """Case response."""

    id: UUID
    case_number: str
    title: str
    description: str | None
    severity: Severity
    priority: Priority
    status: CaseStatus
    assignee_id: UUID | None
    assignee_name: str | None = None
    created_by: UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    tags: list[str]
    mitre_tactics: list[str]
    mitre_techniques: list[str]
    metadata: dict
    evidence_count: int = 0

    class Config:
        from_attributes = True


class CaseListResponse(BaseModel):
    """Paginated case list response."""

    items: list[CaseResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TimelineEvent(BaseModel):
    """Timeline event for a case."""

    id: str
    timestamp: datetime
    title: str
    description: str | None = None
    category: str | None = None
    source: str | None = None
    entities: dict = {}
    evidence_id: UUID | None = None
    created_by: str | None = None
    tags: list[str] = []


class TimelineEventCreate(BaseModel):
    """Create timeline event request."""

    timestamp: datetime
    title: str
    description: str | None = None
    category: str | None = None
    source: str | None = None
    entities: dict = {}
    evidence_id: UUID | None = None
    tags: list[str] = []


async def generate_case_number(db: AsyncSession) -> str:
    """Generate unique case number."""
    year = datetime.now().year
    prefix = f"{settings.case_number_prefix}-{year}"

    # Get the count of cases this year
    result = await db.execute(
        select(func.count(Case.id)).where(Case.case_number.like(f"{prefix}-%"))
    )
    count = result.scalar() or 0

    return f"{prefix}-{count + 1:04d}"


@router.get("", response_model=CaseListResponse)
async def list_cases(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: CaseStatus | None = None,
    severity: Severity | None = None,
    assignee_id: UUID | None = None,
    search: str | None = None,
) -> CaseListResponse:
    """List cases with filtering and pagination."""
    query = select(Case).options(
        selectinload(Case.assignee),
        selectinload(Case.created_by_user),
    )

    # Apply filters
    if status:
        query = query.where(Case.status == status)
    if severity:
        query = query.where(Case.severity == severity)
    if assignee_id:
        query = query.where(Case.assignee_id == assignee_id)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Case.title.ilike(search_filter))
            | (Case.case_number.ilike(search_filter))
            | (Case.description.ilike(search_filter))
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(Case.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    cases = result.scalars().all()

    items = [
        CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            severity=case.severity,
            priority=case.priority,
            status=case.status,
            assignee_id=case.assignee_id,
            assignee_name=case.assignee.display_name if case.assignee else None,
            created_by=case.created_by,
            created_by_name=(
                case.created_by_user.display_name if case.created_by_user else None
            ),
            created_at=case.created_at,
            updated_at=case.updated_at,
            closed_at=case.closed_at,
            tags=case.tags,
            mitre_tactics=case.mitre_tactics,
            mitre_techniques=case.mitre_techniques,
            metadata=case.case_metadata,
            evidence_count=len(case.evidence) if hasattr(case, "evidence") else 0,
        )
        for case in cases
    ]

    return CaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_data: CaseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CaseResponse:
    """Create a new case."""
    case_number = await generate_case_number(db)

    case = Case(
        case_number=case_number,
        title=case_data.title,
        description=case_data.description,
        severity=case_data.severity,
        priority=case_data.priority,
        assignee_id=case_data.assignee_id,
        created_by=current_user.id,
        tags=case_data.tags,
        mitre_tactics=case_data.mitre_tactics,
        mitre_techniques=case_data.mitre_techniques,
        case_metadata=case_data.metadata,
    )

    db.add(case)
    await db.commit()
    await db.refresh(case)

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        severity=case.severity,
        priority=case.priority,
        status=case.status,
        assignee_id=case.assignee_id,
        created_by=case.created_by,
        created_by_name=current_user.display_name,
        created_at=case.created_at,
        updated_at=case.updated_at,
        closed_at=case.closed_at,
        tags=case.tags,
        mitre_tactics=case.mitre_tactics,
        mitre_techniques=case.mitre_techniques,
        metadata=case.case_metadata,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CaseResponse:
    """Get case by ID."""
    query = (
        select(Case)
        .options(
            selectinload(Case.assignee),
            selectinload(Case.created_by_user),
            selectinload(Case.evidence),
        )
        .where(Case.id == case_id)
    )

    result = await db.execute(query)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        severity=case.severity,
        priority=case.priority,
        status=case.status,
        assignee_id=case.assignee_id,
        assignee_name=case.assignee.display_name if case.assignee else None,
        created_by=case.created_by,
        created_by_name=(
            case.created_by_user.display_name if case.created_by_user else None
        ),
        created_at=case.created_at,
        updated_at=case.updated_at,
        closed_at=case.closed_at,
        tags=case.tags,
        mitre_tactics=case.mitre_tactics,
        mitre_techniques=case.mitre_techniques,
        metadata=case.case_metadata,
        evidence_count=len(case.evidence),
    )


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    case_data: CaseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CaseResponse:
    """Update case."""
    query = select(Case).where(Case.id == case_id)
    result = await db.execute(query)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    # Update fields
    update_data = case_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Map 'metadata' from the API to 'case_metadata' on the model
        if field == "metadata":
            setattr(case, "case_metadata", value)
        else:
            setattr(case, field, value)

    # Handle status transitions
    if case_data.status == CaseStatus.CLOSED and not case.closed_at:
        case.closed_at = datetime.now(UTC)
    elif case_data.status != CaseStatus.CLOSED:
        case.closed_at = None

    await db.commit()
    await db.refresh(case)

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        severity=case.severity,
        priority=case.priority,
        status=case.status,
        assignee_id=case.assignee_id,
        created_by=case.created_by,
        created_at=case.created_at,
        updated_at=case.updated_at,
        closed_at=case.closed_at,
        tags=case.tags,
        mitre_tactics=case.mitre_tactics,
        mitre_techniques=case.mitre_techniques,
        metadata=case.case_metadata,
    )


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete case."""
    query = select(Case).where(Case.id == case_id)
    result = await db.execute(query)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    await db.delete(case)
    await db.commit()


@router.get("/{case_id}/timeline", response_model=list[TimelineEvent])
async def get_case_timeline(
    case_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[TimelineEvent]:
    """Get timeline events for a case."""
    from app.database import get_elasticsearch, get_settings

    settings = get_settings()
    es = await get_elasticsearch()

    # Verify case exists
    query = select(Case).where(Case.id == case_id)
    result = await db.execute(query)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    # Query Elasticsearch for timeline events
    try:
        response = await es.search(
            index=f"{settings.elasticsearch_index_prefix}-timeline-*",
            body={
                "query": {"term": {"case_id": str(case_id)}},
                "sort": [{"@timestamp": {"order": "asc"}}],
                "size": 1000,
            },
        )

        events = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            events.append(
                TimelineEvent(
                    id=hit["_id"],
                    timestamp=source.get("@timestamp"),
                    title=source.get("title", ""),
                    description=source.get("description"),
                    category=source.get("category"),
                    source=source.get("source"),
                    entities=source.get("entities", {}),
                    evidence_id=source.get("evidence_id"),
                    created_by=source.get("created_by"),
                    tags=source.get("tags", []),
                )
            )

        return events

    except Exception:
        return []


@router.post("/{case_id}/timeline", response_model=TimelineEvent, status_code=status.HTTP_201_CREATED)
async def add_timeline_event(
    case_id: UUID,
    event_data: TimelineEventCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TimelineEvent:
    """Add a timeline event to a case."""
    from app.database import get_elasticsearch, get_settings

    settings = get_settings()
    es = await get_elasticsearch()

    # Verify case exists
    query = select(Case).where(Case.id == case_id)
    result = await db.execute(query)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    # Index the event
    doc = {
        "@timestamp": event_data.timestamp.isoformat(),
        "case_id": str(case_id),
        "title": event_data.title,
        "description": event_data.description,
        "category": event_data.category,
        "source": event_data.source,
        "entities": event_data.entities,
        "evidence_id": str(event_data.evidence_id) if event_data.evidence_id else None,
        "created_by": current_user.username,
        "tags": event_data.tags,
    }

    response = await es.index(
        index=f"{settings.elasticsearch_index_prefix}-timeline-{datetime.now().strftime('%Y.%m')}",
        body=doc,
        refresh=True,
    )

    return TimelineEvent(
        id=response["_id"],
        timestamp=event_data.timestamp,
        title=event_data.title,
        description=event_data.description,
        category=event_data.category,
        source=event_data.source,
        entities=event_data.entities,
        evidence_id=event_data.evidence_id,
        created_by=current_user.username,
        tags=event_data.tags,
    )
