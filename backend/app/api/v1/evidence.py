"""Evidence API endpoints with chain of custody tracking."""

import hashlib
import os
from datetime import datetime
from typing import Annotated
from uuid import UUID

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.case import Case
from app.models.evidence import CustodyAction, CustodyEvent, Evidence, EvidenceStatus, EvidenceType
from app.models.user import User

router = APIRouter()
settings = get_settings()


class EvidenceResponse(BaseModel):
    """Evidence response."""

    id: UUID
    case_id: UUID
    filename: str
    original_filename: str | None
    file_size: int | None
    sha256: str | None
    sha1: str | None
    md5: str | None
    mime_type: str | None
    evidence_type: EvidenceType
    status: EvidenceStatus
    source_host: str | None
    collected_at: datetime | None
    collected_by: str | None
    uploaded_by: UUID | None
    uploader_name: str | None = None
    uploaded_at: datetime
    description: str | None
    metadata: dict

    class Config:
        from_attributes = True


class CustodyEventResponse(BaseModel):
    """Custody event response."""

    id: UUID
    evidence_id: UUID
    action: CustodyAction
    actor_id: UUID | None
    actor_name: str | None
    ip_address: str | None
    user_agent: str | None
    details: dict
    created_at: datetime

    class Config:
        from_attributes = True


class EvidenceUpdate(BaseModel):
    """Evidence update request."""

    evidence_type: EvidenceType | None = None
    status: EvidenceStatus | None = None
    description: str | None = None
    source_host: str | None = None
    collected_at: datetime | None = None
    collected_by: str | None = None
    metadata: dict | None = None


class EvidenceListResponse(BaseModel):
    """Paginated evidence list response."""

    items: list[EvidenceResponse]
    total: int
    page: int
    page_size: int
    pages: int


async def compute_hashes(file_path: str) -> dict[str, str]:
    """Compute SHA256, SHA1, and MD5 hashes of a file."""
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1()
    md5 = hashlib.md5()

    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(8192):
            sha256.update(chunk)
            sha1.update(chunk)
            md5.update(chunk)

    return {
        "sha256": sha256.hexdigest(),
        "sha1": sha1.hexdigest(),
        "md5": md5.hexdigest(),
    }


async def log_custody_event(
    db: AsyncSession,
    evidence_id: UUID,
    action: CustodyAction,
    user: User,
    request: Request,
    details: dict | None = None,
) -> CustodyEvent:
    """Log a chain of custody event."""
    event = CustodyEvent(
        evidence_id=evidence_id,
        action=action,
        actor_id=user.id,
        actor_name=user.display_name or user.username,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details=details or {},
    )
    db.add(event)
    return event


@router.get("", response_model=EvidenceListResponse)
async def list_evidence(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    case_id: UUID | None = Query(None, description="Filter by case ID"),
    evidence_type: EvidenceType | None = Query(None, description="Filter by evidence type"),
    status_filter: EvidenceStatus | None = Query(None, alias="status", description="Filter by status"),
    search: str | None = Query(None, description="Search in filename/description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> EvidenceListResponse:
    """List evidence with filtering and pagination."""
    query = select(Evidence).options(selectinload(Evidence.uploader))

    # Apply filters
    if case_id:
        query = query.where(Evidence.case_id == case_id)
    if evidence_type:
        query = query.where(Evidence.evidence_type == evidence_type)
    if status_filter:
        query = query.where(Evidence.status == status_filter)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Evidence.filename.ilike(search_filter))
            | (Evidence.original_filename.ilike(search_filter))
            | (Evidence.description.ilike(search_filter))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Evidence.uploaded_at.desc())

    result = await db.execute(query)
    evidence_list = result.scalars().all()

    items = [
        EvidenceResponse(
            id=e.id,
            case_id=e.case_id,
            filename=e.filename,
            original_filename=e.original_filename,
            file_size=e.file_size,
            sha256=e.sha256,
            sha1=e.sha1,
            md5=e.md5,
            mime_type=e.mime_type,
            evidence_type=e.evidence_type,
            status=e.status,
            source_host=e.source_host,
            collected_at=e.collected_at,
            collected_by=e.collected_by,
            uploaded_by=e.uploaded_by,
            uploader_name=e.uploader.display_name if e.uploader else None,
            uploaded_at=e.uploaded_at,
            description=e.description,
            metadata=e.metadata,
        )
        for e in evidence_list
    ]

    pages = (total + page_size - 1) // page_size if page_size else 1

    return EvidenceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.patch("/{evidence_id}", response_model=EvidenceResponse)
async def update_evidence(
    evidence_id: UUID,
    updates: EvidenceUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EvidenceResponse:
    """Update evidence metadata."""
    query = (
        select(Evidence)
        .options(selectinload(Evidence.uploader))
        .where(Evidence.id == evidence_id)
    )
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    changes = {}
    for field, value in update_data.items():
        if value is not None:
            old_value = getattr(evidence, field)
            setattr(evidence, field, value)
            changes[field] = {"old": str(old_value), "new": str(value)}

    if changes:
        # Log update event
        await log_custody_event(
            db=db,
            evidence_id=evidence.id,
            action=CustodyAction.MODIFIED,
            user=current_user,
            request=request,
            details={"changes": changes},
        )

    await db.commit()
    await db.refresh(evidence)

    return EvidenceResponse(
        id=evidence.id,
        case_id=evidence.case_id,
        filename=evidence.filename,
        original_filename=evidence.original_filename,
        file_size=evidence.file_size,
        sha256=evidence.sha256,
        sha1=evidence.sha1,
        md5=evidence.md5,
        mime_type=evidence.mime_type,
        evidence_type=evidence.evidence_type,
        status=evidence.status,
        source_host=evidence.source_host,
        collected_at=evidence.collected_at,
        collected_by=evidence.collected_by,
        uploaded_by=evidence.uploaded_by,
        uploader_name=evidence.uploader.display_name if evidence.uploader else None,
        uploaded_at=evidence.uploaded_at,
        description=evidence.description,
        metadata=evidence.metadata,
    )


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Download evidence file."""
    query = select(Evidence).where(Evidence.id == evidence_id)
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    if not evidence.file_path or not os.path.exists(evidence.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found on disk",
        )

    # Log download event
    await log_custody_event(
        db=db,
        evidence_id=evidence.id,
        action=CustodyAction.DOWNLOADED,
        user=current_user,
        request=request,
    )
    await db.commit()

    return FileResponse(
        path=evidence.file_path,
        filename=evidence.original_filename or evidence.filename,
        media_type=evidence.mime_type or "application/octet-stream",
    )


@router.post("/upload", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    case_id: UUID = Form(...),
    evidence_type: EvidenceType = Form(EvidenceType.OTHER),
    source_host: str | None = Form(None),
    collected_at: datetime | None = Form(None),
    collected_by: str | None = Form(None),
    description: str | None = Form(None),
) -> EvidenceResponse:
    """Upload evidence file with automatic hashing."""
    # Verify case exists
    query = select(Case).where(Case.id == case_id)
    result = await db.execute(query)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    # Create evidence directory
    evidence_dir = os.path.join(settings.evidence_path, str(case_id))
    os.makedirs(evidence_dir, exist_ok=True)

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(evidence_dir, safe_filename)

    # Save file
    file_size = 0
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(8192):
            await f.write(chunk)
            file_size += len(chunk)

    # Compute hashes
    hashes = await compute_hashes(file_path)

    # Detect MIME type
    try:
        import magic
        mime_type = magic.from_file(file_path, mime=True)
    except Exception:
        mime_type = file.content_type

    # Create evidence record
    evidence = Evidence(
        case_id=case_id,
        filename=safe_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        sha256=hashes["sha256"],
        sha1=hashes["sha1"],
        md5=hashes["md5"],
        mime_type=mime_type,
        evidence_type=evidence_type,
        status=EvidenceStatus.READY,
        source_host=source_host,
        collected_at=collected_at,
        collected_by=collected_by,
        uploaded_by=current_user.id,
        description=description,
    )

    db.add(evidence)
    await db.flush()

    # Log custody event
    await log_custody_event(
        db=db,
        evidence_id=evidence.id,
        action=CustodyAction.UPLOADED,
        user=current_user,
        request=request,
        details={
            "original_filename": file.filename,
            "file_size": file_size,
            "sha256": hashes["sha256"],
        },
    )

    await db.commit()
    await db.refresh(evidence)

    return EvidenceResponse(
        id=evidence.id,
        case_id=evidence.case_id,
        filename=evidence.filename,
        original_filename=evidence.original_filename,
        file_size=evidence.file_size,
        sha256=evidence.sha256,
        sha1=evidence.sha1,
        md5=evidence.md5,
        mime_type=evidence.mime_type,
        evidence_type=evidence.evidence_type,
        status=evidence.status,
        source_host=evidence.source_host,
        collected_at=evidence.collected_at,
        collected_by=evidence.collected_by,
        uploaded_by=evidence.uploaded_by,
        uploader_name=current_user.display_name,
        uploaded_at=evidence.uploaded_at,
        description=evidence.description,
        metadata=evidence.metadata,
    )


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EvidenceResponse:
    """Get evidence by ID."""
    query = (
        select(Evidence)
        .options(selectinload(Evidence.uploader))
        .where(Evidence.id == evidence_id)
    )
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # Log access
    await log_custody_event(
        db=db,
        evidence_id=evidence.id,
        action=CustodyAction.ACCESSED,
        user=current_user,
        request=request,
    )
    await db.commit()

    return EvidenceResponse(
        id=evidence.id,
        case_id=evidence.case_id,
        filename=evidence.filename,
        original_filename=evidence.original_filename,
        file_size=evidence.file_size,
        sha256=evidence.sha256,
        sha1=evidence.sha1,
        md5=evidence.md5,
        mime_type=evidence.mime_type,
        evidence_type=evidence.evidence_type,
        status=evidence.status,
        source_host=evidence.source_host,
        collected_at=evidence.collected_at,
        collected_by=evidence.collected_by,
        uploaded_by=evidence.uploaded_by,
        uploader_name=evidence.uploader.display_name if evidence.uploader else None,
        uploaded_at=evidence.uploaded_at,
        description=evidence.description,
        metadata=evidence.metadata,
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    evidence_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete evidence (soft delete - marks as deleted but retains custody chain)."""
    query = select(Evidence).where(Evidence.id == evidence_id)
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # Log deletion event before deleting
    await log_custody_event(
        db=db,
        evidence_id=evidence.id,
        action=CustodyAction.DELETED,
        user=current_user,
        request=request,
        details={
            "sha256": evidence.sha256,
            "filename": evidence.original_filename,
        },
    )

    # Remove physical file
    if evidence.file_path and os.path.exists(evidence.file_path):
        os.remove(evidence.file_path)

    await db.delete(evidence)
    await db.commit()


@router.get("/{evidence_id}/custody", response_model=list[CustodyEventResponse])
async def get_custody_chain(
    evidence_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustodyEventResponse]:
    """Get chain of custody for evidence."""
    query = (
        select(CustodyEvent)
        .where(CustodyEvent.evidence_id == evidence_id)
        .order_by(CustodyEvent.created_at.asc())
    )
    result = await db.execute(query)
    events = result.scalars().all()

    return [
        CustodyEventResponse(
            id=event.id,
            evidence_id=event.evidence_id,
            action=event.action,
            actor_id=event.actor_id,
            actor_name=event.actor_name,
            ip_address=str(event.ip_address) if event.ip_address else None,
            user_agent=event.user_agent,
            details=event.details,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.post("/{evidence_id}/verify", response_model=dict)
async def verify_evidence_integrity(
    evidence_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Verify evidence file integrity by recalculating hashes."""
    query = select(Evidence).where(Evidence.id == evidence_id)
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    if not evidence.file_path or not os.path.exists(evidence.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found",
        )

    # Recompute hashes
    current_hashes = await compute_hashes(evidence.file_path)

    # Compare
    integrity_valid = (
        current_hashes["sha256"] == evidence.sha256
        and current_hashes["sha1"] == evidence.sha1
        and current_hashes["md5"] == evidence.md5
    )

    # Log verification
    await log_custody_event(
        db=db,
        evidence_id=evidence.id,
        action=CustodyAction.VERIFIED,
        user=current_user,
        request=request,
        details={
            "integrity_valid": integrity_valid,
            "computed_sha256": current_hashes["sha256"],
            "stored_sha256": evidence.sha256,
        },
    )
    await db.commit()

    return {
        "evidence_id": str(evidence_id),
        "integrity_valid": integrity_valid,
        "stored_hashes": {
            "sha256": evidence.sha256,
            "sha1": evidence.sha1,
            "md5": evidence.md5,
        },
        "computed_hashes": current_hashes,
    }
