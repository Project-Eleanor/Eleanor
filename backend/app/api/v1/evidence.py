"""Evidence API endpoints with chain of custody tracking."""

import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.storage import get_storage_adapter
from app.adapters.storage.local import LocalStorageAdapter
from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.case import Case
from app.models.evidence import CustodyAction, CustodyEvent, Evidence, EvidenceStatus, EvidenceType
from app.models.user import User

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


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
    uploaded_at: datetime | None = None
    description: str | None = None
    metadata: dict | None = None

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
    details: dict | None = {}
    created_at: datetime | None = None

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


async def compute_hashes_from_storage(storage_key: str) -> dict[str, str]:
    """Compute SHA256, SHA1, and MD5 hashes of a stored file."""
    storage = get_storage_adapter()
    return await storage.compute_hashes(storage_key)


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
    status_filter: EvidenceStatus | None = Query(
        None, alias="status", description="Filter by status"
    ),
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
            metadata=e.evidence_metadata,
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
        select(Evidence).options(selectinload(Evidence.uploader)).where(Evidence.id == evidence_id)
    )
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # Apply updates - map schema field names to model attribute names
    field_mapping = {"metadata": "evidence_metadata"}
    update_data = updates.model_dump(exclude_unset=True)
    changes = {}
    for field, value in update_data.items():
        if value is not None:
            # Map schema field name to model attribute name if different
            model_field = field_mapping.get(field, field)
            old_value = getattr(evidence, model_field)
            setattr(evidence, model_field, value)
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
        metadata=evidence.evidence_metadata,
    )


@router.get("/{evidence_id}/download", response_model=None)
async def download_evidence(
    evidence_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Download evidence file."""
    query = select(Evidence).where(Evidence.id == evidence_id)
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    if not evidence.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file path not found",
        )

    storage = get_storage_adapter()

    # Check if file exists in storage
    if not await storage.exists(evidence.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found in storage",
        )

    # Log download event
    await log_custody_event(
        db=db,
        evidence_id=evidence.id,
        action=CustodyAction.DOWNLOADED,
        user=current_user,
        request=request,
        details={"storage_backend": storage.name},
    )
    await db.commit()

    # For local storage, use FileResponse for efficiency
    if isinstance(storage, LocalStorageAdapter):
        return FileResponse(
            path=storage.get_file_path(evidence.file_path),
            filename=evidence.original_filename or evidence.filename,
            media_type=evidence.mime_type or "application/octet-stream",
        )

    # For cloud storage, stream the content
    async def stream_content():
        async for chunk in storage.stream_download(evidence.file_path):
            yield chunk

    return StreamingResponse(
        stream_content(),
        media_type=evidence.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{evidence.original_filename or evidence.filename}"',
            "Content-Length": str(evidence.file_size) if evidence.file_size else "",
        },
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

    # Get storage adapter
    storage = get_storage_adapter()

    # Generate storage key
    storage_key = storage.generate_key(case_id, file.filename or "unnamed")

    # Detect MIME type from content if possible
    mime_type = file.content_type
    first_chunk = await file.read(8192)
    await file.seek(0)  # Reset to beginning

    try:
        import magic

        mime_type = magic.from_buffer(first_chunk, mime=True)
    except Exception:
        pass

    # Upload file with hash computation
    # Read file content for upload
    file_content = BytesIO()
    while chunk := await file.read(8192):
        file_content.write(chunk)
    file_content.seek(0)

    upload_result = await storage.upload_file(
        file=file_content,
        key=storage_key,
        content_type=mime_type,
        metadata={
            "case_id": str(case_id),
            "original_filename": file.filename or "unnamed",
            "uploaded_by": str(current_user.id),
        },
    )

    # Create evidence record
    evidence = Evidence(
        case_id=case_id,
        filename=os.path.basename(storage_key),
        original_filename=file.filename,
        file_path=storage_key,  # Now stores storage key instead of local path
        file_size=upload_result.size,
        sha256=upload_result.sha256,
        sha1=upload_result.sha1,
        md5=upload_result.md5,
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
            "file_size": upload_result.size,
            "sha256": upload_result.sha256,
            "storage_backend": storage.name,
            "storage_url": upload_result.storage_url,
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
        metadata=evidence.evidence_metadata,
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
        select(Evidence).options(selectinload(Evidence.uploader)).where(Evidence.id == evidence_id)
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
        metadata=evidence.evidence_metadata,
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

    storage = get_storage_adapter()

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
            "storage_backend": storage.name,
        },
    )

    # Remove file from storage
    if evidence.file_path:
        try:
            await storage.delete(evidence.file_path)
        except Exception as e:
            logger.warning("Failed to delete evidence file from storage: %s", e)

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

    if not evidence.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file path not found",
        )

    storage = get_storage_adapter()

    if not await storage.exists(evidence.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found in storage",
        )

    # Recompute hashes
    current_hashes = await compute_hashes_from_storage(evidence.file_path)

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
            "storage_backend": storage.name,
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
        "storage_backend": storage.name,
    }


@router.get("/{evidence_id}/download-url")
async def get_evidence_download_url(
    evidence_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    expires_in: int = Query(3600, ge=60, le=86400, description="URL expiration in seconds"),
) -> dict:
    """Get a presigned download URL for evidence.

    Useful for large files when using cloud storage backends.
    For local storage, returns a direct file path URL.
    """
    query = select(Evidence).where(Evidence.id == evidence_id)
    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    if not evidence.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file path not found",
        )

    storage = get_storage_adapter()

    if not await storage.exists(evidence.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found in storage",
        )

    # Generate presigned URL
    download_url = await storage.get_download_url(
        key=evidence.file_path,
        expires_in=expires_in,
        filename=evidence.original_filename or evidence.filename,
    )

    # Log access
    await log_custody_event(
        db=db,
        evidence_id=evidence.id,
        action=CustodyAction.ACCESSED,
        user=current_user,
        request=request,
        details={
            "action": "download_url_generated",
            "expires_in": expires_in,
            "storage_backend": storage.name,
        },
    )
    await db.commit()

    return {
        "evidence_id": str(evidence_id),
        "download_url": download_url,
        "expires_in": expires_in,
        "filename": evidence.original_filename or evidence.filename,
        "storage_backend": storage.name,
    }


@router.get("/storage/stats")
async def get_storage_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    prefix: str = Query("", description="Filter by key prefix"),
) -> dict:
    """Get storage usage statistics."""
    storage = get_storage_adapter()
    stats = await storage.get_stats(prefix)

    health = await storage.health_check()

    return {
        "total_files": stats.total_files,
        "total_size": stats.total_size,
        "total_size_human": _human_readable_size(stats.total_size),
        "bucket": stats.bucket,
        "prefix": stats.prefix,
        "backend": storage.name,
        "health": health,
    }


def _human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
