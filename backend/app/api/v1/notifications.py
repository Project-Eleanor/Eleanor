"""Notification API endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.exceptions import NotFoundError
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationSeverity,
    NotificationType,
)
from app.models.user import User
from app.websocket import publish_notification

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class NotificationResponse(BaseModel):
    """Notification response."""

    id: UUID
    type: str
    severity: str
    title: str
    body: str | None
    link: str | None
    icon: str | None
    data: dict | None
    read: bool
    read_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated notification list response."""

    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationCreate(BaseModel):
    """Create notification request (admin/system use)."""

    user_id: UUID
    type: NotificationType
    severity: NotificationSeverity = NotificationSeverity.INFO
    title: str
    body: str | None = None
    link: str | None = None
    icon: str | None = None
    data: dict | None = None


class MarkReadRequest(BaseModel):
    """Mark notifications as read request."""

    notification_ids: list[UUID]


class NotificationPreferenceResponse(BaseModel):
    """Notification preferences response."""

    email_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    type_preferences: dict
    quiet_hours_enabled: bool
    quiet_hours_start: str | None
    quiet_hours_end: str | None

    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    """Update notification preferences request."""

    email_enabled: bool | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None
    type_preferences: dict | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None


# =============================================================================
# Notification Endpoints
# =============================================================================


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: NotificationType | None = Query(None),
) -> NotificationListResponse:
    """List notifications for the current user."""
    offset = (page - 1) * page_size

    # Base query
    base_query = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.dismissed == False  # noqa: E712
    )

    if unread_only:
        base_query = base_query.where(Notification.read == False)  # noqa: E712

    if notification_type:
        base_query = base_query.where(Notification.type == notification_type)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get unread count
    unread_query = select(func.count()).where(
        Notification.user_id == current_user.id,
        Notification.read == False,  # noqa: E712
        Notification.dismissed == False  # noqa: E712
    )
    unread_result = await db.execute(unread_query)
    unread_count = unread_result.scalar() or 0

    # Get paginated results
    query = (
        base_query
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    notifications = result.scalars().all()

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count")
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get count of unread notifications."""
    query = select(func.count()).where(
        Notification.user_id == current_user.id,
        Notification.read == False,  # noqa: E712
        Notification.dismissed == False  # noqa: E712
    )
    result = await db.execute(query)
    count = result.scalar() or 0

    return {"unread_count": count}


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponse:
    """Get a specific notification."""
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotFoundError("Notification", str(notification_id))

    return NotificationResponse.model_validate(notification)


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Mark a notification as read."""
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotFoundError("Notification", str(notification_id))

    notification.read = True
    notification.read_at = datetime.utcnow()
    await db.commit()

    return {"success": True}


@router.post("/mark-read")
async def mark_multiple_as_read(
    request: MarkReadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Mark multiple notifications as read."""
    stmt = (
        update(Notification)
        .where(
            Notification.id.in_(request.notification_ids),
            Notification.user_id == current_user.id,
        )
        .values(read=True, read_at=datetime.utcnow())
    )
    await db.execute(stmt)
    await db.commit()

    return {"success": True, "count": len(request.notification_ids)}


@router.post("/mark-all-read")
async def mark_all_as_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Mark all notifications as read."""
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.read == False,  # noqa: E712
        )
        .values(read=True, read_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    await db.commit()

    return {"success": True, "count": result.rowcount}


@router.delete("/{notification_id}")
async def dismiss_notification(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Dismiss (soft delete) a notification."""
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotFoundError("Notification", str(notification_id))

    notification.dismissed = True
    await db.commit()

    return {"success": True}


# =============================================================================
# Preferences Endpoints
# =============================================================================


@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_preferences(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationPreferenceResponse:
    """Get notification preferences for the current user."""
    query = select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id
    )
    result = await db.execute(query)
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create default preferences
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)

    return NotificationPreferenceResponse.model_validate(prefs)


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
async def update_preferences(
    updates: NotificationPreferenceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationPreferenceResponse:
    """Update notification preferences."""
    query = select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id
    )
    result = await db.execute(query)
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)

    return NotificationPreferenceResponse.model_validate(prefs)


# =============================================================================
# Admin/System Endpoints
# =============================================================================


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_data: NotificationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponse:
    """Create a notification (admin/system use)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    notification = Notification(
        user_id=notification_data.user_id,
        type=notification_data.type,
        severity=notification_data.severity,
        title=notification_data.title,
        body=notification_data.body,
        link=notification_data.link,
        icon=notification_data.icon,
        data=notification_data.data,
    )

    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Send real-time notification via WebSocket
    await publish_notification(
        title=notification.title,
        body=notification.body or "",
        severity=notification.severity,
        user_id=str(notification.user_id),
        data={
            "notification_id": str(notification.id),
            "type": notification.type,
            "link": notification.link,
        },
    )

    return NotificationResponse.model_validate(notification)


# =============================================================================
# Helper Function for Creating Notifications
# =============================================================================


async def send_notification(
    db: AsyncSession,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    body: str | None = None,
    severity: NotificationSeverity = NotificationSeverity.INFO,
    link: str | None = None,
    icon: str | None = None,
    data: dict | None = None,
) -> Notification:
    """Helper function to create and send a notification."""
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        severity=severity,
        title=title,
        body=body,
        link=link,
        icon=icon,
        data=data,
    )

    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Send real-time notification via WebSocket
    await publish_notification(
        title=title,
        body=body or "",
        severity=severity,
        user_id=str(user_id),
        data={
            "notification_id": str(notification.id),
            "type": notification_type,
            "link": link,
            **(data or {}),
        },
    )

    return notification
