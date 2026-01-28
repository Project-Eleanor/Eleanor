"""Parsing API endpoints for evidence processing.

Provides endpoints for submitting, monitoring, and managing parsing jobs
that process evidence files and index events to Elasticsearch.
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.evidence import Evidence
from app.models.parsing_job import ParsingJob, ParsingJobStatus
from app.models.user import User
from app.parsers.registry import get_registry, load_builtin_parsers

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic schemas
class ParsingSubmitRequest(BaseModel):
    """Request to submit a parsing job."""

    evidence_id: UUID = Field(..., description="UUID of evidence to parse")
    parser_hint: str | None = Field(
        None,
        description="Parser name hint (e.g., 'windows_registry', 'prefetch')",
    )
    config: dict | None = Field(
        None,
        description="Optional parser configuration",
    )
    priority: str = Field(
        "default",
        description="Job priority: high, default, or low",
    )


class ParsingJobResponse(BaseModel):
    """Parsing job status response."""

    id: UUID
    evidence_id: UUID
    case_id: UUID
    celery_task_id: str | None
    parser_type: str
    status: ParsingJobStatus
    events_parsed: int
    events_indexed: int
    events_failed: int
    progress_percent: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    results_summary: dict | None

    class Config:
        from_attributes = True


class ParsingJobListResponse(BaseModel):
    """List of parsing jobs response."""

    items: list[ParsingJobResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ParserInfo(BaseModel):
    """Parser information."""

    name: str
    description: str
    category: str
    extensions: list[str]
    mime_types: list[str]


class ParsersListResponse(BaseModel):
    """List of available parsers."""

    parsers: list[ParserInfo]
    total: int


@router.post("/submit", response_model=ParsingJobResponse)
async def submit_parsing_job(
    request: ParsingSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ParsingJobResponse:
    """Submit a new parsing job.

    Creates a parsing job record and enqueues a Celery task to process
    the evidence file.
    """
    # Verify evidence exists
    evidence = await db.get(Evidence, request.evidence_id)
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {request.evidence_id} not found",
        )

    # Ensure parsers are loaded
    load_builtin_parsers()

    # Detect parser if not specified
    parser_type = request.parser_hint or "auto"
    if request.parser_hint:
        registry = get_registry()
        parser = registry.get(request.parser_hint)
        if not parser:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser: {request.parser_hint}",
            )
        parser_type = parser.name

    # Create parsing job record
    job = ParsingJob(
        evidence_id=request.evidence_id,
        case_id=evidence.case_id,
        parser_type=parser_type,
        parser_hint=request.parser_hint,
        config=request.config or {},
        submitted_by=current_user.id,
        status=ParsingJobStatus.PENDING,
    )
    db.add(job)
    await db.flush()

    # Submit Celery task
    try:
        from app.tasks.parsing import parse_evidence

        # Map priority to queue
        queue_map = {
            "high": "high",
            "default": "default",
            "low": "low",
        }
        queue = queue_map.get(request.priority, "default")

        task = parse_evidence.apply_async(
            kwargs={
                "job_id": str(job.id),
                "evidence_id": str(request.evidence_id),
                "case_id": str(evidence.case_id),
                "parser_hint": request.parser_hint,
                "config": request.config or {},
            },
            queue=queue,
        )

        job.mark_queued(task.id)
        await db.commit()

        logger.info(f"Submitted parsing job {job.id} for evidence {evidence.filename}")

    except Exception as e:
        logger.error(f"Failed to submit Celery task: {e}")
        job.mark_failed(f"Failed to submit task: {e}")
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit parsing job: {e}",
        )

    return ParsingJobResponse(
        id=job.id,
        evidence_id=job.evidence_id,
        case_id=job.case_id,
        celery_task_id=job.celery_task_id,
        parser_type=job.parser_type,
        status=job.status,
        events_parsed=job.events_parsed,
        events_indexed=job.events_indexed,
        events_failed=job.events_failed,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        results_summary=job.results_summary,
    )


@router.get("/jobs/{job_id}", response_model=ParsingJobResponse)
async def get_parsing_job(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ParsingJobResponse:
    """Get parsing job status by ID."""
    job = await db.get(ParsingJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing job {job_id} not found",
        )

    # Optionally update status from Celery if running
    if job.status == ParsingJobStatus.QUEUED and job.celery_task_id:
        try:
            from app.tasks.celery_app import celery_app

            result = celery_app.AsyncResult(job.celery_task_id)
            if result.state == "PROGRESS":
                meta = result.info or {}
                job.events_parsed = meta.get("events_parsed", job.events_parsed)
                job.events_indexed = meta.get("events_indexed", job.events_indexed)
                job.progress_percent = meta.get("progress", job.progress_percent)
        except Exception as e:
            logger.warning(f"Failed to get Celery task status: {e}")

    return ParsingJobResponse(
        id=job.id,
        evidence_id=job.evidence_id,
        case_id=job.case_id,
        celery_task_id=job.celery_task_id,
        parser_type=job.parser_type,
        status=job.status,
        events_parsed=job.events_parsed,
        events_indexed=job.events_indexed,
        events_failed=job.events_failed,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        results_summary=job.results_summary,
    )


@router.get("/jobs", response_model=ParsingJobListResponse)
async def list_parsing_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    case_id: UUID | None = Query(None, description="Filter by case"),
    evidence_id: UUID | None = Query(None, description="Filter by evidence"),
    status_filter: ParsingJobStatus | None = Query(
        None, alias="status", description="Filter by status"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> ParsingJobListResponse:
    """List parsing jobs with optional filtering."""
    # Build query
    query = select(ParsingJob)

    if case_id:
        query = query.where(ParsingJob.case_id == case_id)
    if evidence_id:
        query = query.where(ParsingJob.evidence_id == evidence_id)
    if status_filter:
        query = query.where(ParsingJob.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Add pagination and ordering
    query = query.order_by(ParsingJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    jobs = result.scalars().all()

    pages = (total + page_size - 1) // page_size

    return ParsingJobListResponse(
        items=[
            ParsingJobResponse(
                id=job.id,
                evidence_id=job.evidence_id,
                case_id=job.case_id,
                celery_task_id=job.celery_task_id,
                parser_type=job.parser_type,
                status=job.status,
                events_parsed=job.events_parsed,
                events_indexed=job.events_indexed,
                events_failed=job.events_failed,
                progress_percent=job.progress_percent,
                error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=job.duration_seconds,
                results_summary=job.results_summary,
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/jobs/{job_id}/cancel", response_model=ParsingJobResponse)
async def cancel_parsing_job(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ParsingJobResponse:
    """Cancel a running or queued parsing job."""
    job = await db.get(ParsingJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing job {job_id} not found",
        )

    if job.status not in (
        ParsingJobStatus.PENDING,
        ParsingJobStatus.QUEUED,
        ParsingJobStatus.RUNNING,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in {job.status.value} status",
        )

    # Revoke Celery task if exists
    if job.celery_task_id:
        try:
            from app.tasks.parsing import cancel_parsing_job as cancel_task

            cancel_task.delay(str(job_id), job.celery_task_id)
        except Exception as e:
            logger.warning(f"Failed to revoke Celery task: {e}")

    job.mark_cancelled()
    await db.commit()

    logger.info(f"Cancelled parsing job {job_id}")

    return ParsingJobResponse(
        id=job.id,
        evidence_id=job.evidence_id,
        case_id=job.case_id,
        celery_task_id=job.celery_task_id,
        parser_type=job.parser_type,
        status=job.status,
        events_parsed=job.events_parsed,
        events_indexed=job.events_indexed,
        events_failed=job.events_failed,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        results_summary=job.results_summary,
    )


@router.get("/parsers", response_model=ParsersListResponse)
async def list_parsers(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ParsersListResponse:
    """List all available parsers."""
    load_builtin_parsers()
    registry = get_registry()
    parsers_list = registry.list_parsers()

    return ParsersListResponse(
        parsers=[
            ParserInfo(
                name=p["name"],
                description=p["description"],
                category=p["category"],
                extensions=p["extensions"],
                mime_types=p["mime_types"],
            )
            for p in parsers_list
        ],
        total=len(parsers_list),
    )


@router.post("/batch-submit")
async def batch_submit_parsing_jobs(
    evidence_ids: list[UUID],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    parser_hint: str | None = Query(None, description="Parser hint for all jobs"),
) -> dict:
    """Submit parsing jobs for multiple evidence files."""
    jobs_created = []
    errors = []

    for evidence_id in evidence_ids:
        try:
            evidence = await db.get(Evidence, evidence_id)
            if not evidence:
                errors.append(
                    {
                        "evidence_id": str(evidence_id),
                        "error": "Evidence not found",
                    }
                )
                continue

            # Create job
            job = ParsingJob(
                evidence_id=evidence_id,
                case_id=evidence.case_id,
                parser_type=parser_hint or "auto",
                parser_hint=parser_hint,
                config={},
                submitted_by=current_user.id,
                status=ParsingJobStatus.PENDING,
            )
            db.add(job)
            await db.flush()

            # Submit task
            from app.tasks.parsing import parse_evidence

            task = parse_evidence.apply_async(
                kwargs={
                    "job_id": str(job.id),
                    "evidence_id": str(evidence_id),
                    "case_id": str(evidence.case_id),
                    "parser_hint": parser_hint,
                    "config": {},
                },
            )

            job.mark_queued(task.id)
            jobs_created.append(
                {
                    "job_id": str(job.id),
                    "evidence_id": str(evidence_id),
                    "celery_task_id": task.id,
                }
            )

        except Exception as e:
            errors.append(
                {
                    "evidence_id": str(evidence_id),
                    "error": str(e),
                }
            )

    await db.commit()

    return {
        "submitted": len(jobs_created),
        "jobs": jobs_created,
        "errors": errors,
    }
