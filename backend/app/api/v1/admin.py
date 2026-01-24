"""Admin API endpoints for user management and system configuration."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_admin
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import AuthProvider, User

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserCreate(BaseModel):
    """User creation request."""

    username: str
    email: EmailStr | None = None
    display_name: str | None = None
    password: str
    is_admin: bool = False
    roles: list[str] = []


class UserUpdate(BaseModel):
    """User update request."""

    email: EmailStr | None = None
    display_name: str | None = None
    password: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None
    roles: list[str] | None = None


class UserResponse(BaseModel):
    """User response."""

    id: UUID
    username: str
    email: str | None
    display_name: str | None
    auth_provider: str
    is_active: bool
    is_admin: bool
    roles: list[str]
    last_login: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response."""

    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class AuditLogEntry(BaseModel):
    """Audit log entry response."""

    id: UUID
    user_id: UUID | None
    username: str | None
    action: str
    resource_type: str | None
    resource_id: UUID | None
    details: dict
    ip_address: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""

    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


class SystemConfig(BaseModel):
    """System configuration response."""

    app_name: str
    app_version: str
    auth_providers: dict[str, bool]
    features: dict[str, bool]


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_active_admin)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    is_active: bool | None = None,
) -> UserListResponse:
    """List all users."""
    query = select(User)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.username.ilike(search_filter))
            | (User.email.ilike(search_filter))
            | (User.display_name.ilike(search_filter))
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(User.username)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        items=[
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                display_name=user.display_name,
                auth_provider=user.auth_provider.value,
                is_active=user.is_active,
                is_admin=user.is_admin,
                roles=user.roles,
                last_login=user.last_login,
                created_at=user.created_at,
            )
            for user in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_active_admin)],
) -> UserResponse:
    """Create a new user."""
    # Check if username exists
    existing = await db.execute(select(User).where(User.username == user_data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Check if email exists
    if user_data.email:
        existing = await db.execute(select(User).where(User.email == user_data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

    user = User(
        username=user_data.username,
        email=user_data.email,
        display_name=user_data.display_name or user_data.username,
        auth_provider=AuthProvider.SAM,
        password_hash=pwd_context.hash(user_data.password),
        is_admin=user_data.is_admin,
        roles=user_data.roles,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider.value,
        is_active=user.is_active,
        is_admin=user.is_admin,
        roles=user.roles,
        last_login=user.last_login,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_active_admin)],
) -> UserResponse:
    """Update a user."""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update fields
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.display_name is not None:
        user.display_name = user_data.display_name
    if user_data.password is not None:
        user.password_hash = pwd_context.hash(user_data.password)
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin
    if user_data.roles is not None:
        user.roles = user_data.roles

    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider.value,
        is_active=user.is_active,
        is_admin=user.is_admin,
        roles=user.roles,
        last_login=user.last_login,
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_active_admin)],
) -> None:
    """Delete a user."""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    await db.delete(user)
    await db.commit()


@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_active_admin)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = None,
    resource_type: str | None = None,
    user_id: UUID | None = None,
) -> AuditLogResponse:
    """Get audit log entries."""
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    entries = result.scalars().all()

    return AuditLogResponse(
        items=[
            AuditLogEntry(
                id=entry.id,
                user_id=entry.user_id,
                username=entry.username,
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                details=entry.details,
                ip_address=str(entry.ip_address) if entry.ip_address else None,
                created_at=entry.created_at,
            )
            for entry in entries
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/config", response_model=SystemConfig)
async def get_system_config(
    admin: Annotated[User, Depends(get_current_active_admin)],
) -> SystemConfig:
    """Get system configuration."""
    from app.config import get_settings

    settings = get_settings()

    return SystemConfig(
        app_name=settings.app_name,
        app_version=settings.app_version,
        auth_providers={
            "oidc": settings.oidc_enabled,
            "ldap": settings.ldap_enabled,
            "sam": settings.sam_enabled,
        },
        features={
            "debug": settings.debug,
        },
    )
