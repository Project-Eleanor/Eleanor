"""Admin API endpoints for user management and system configuration."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_admin
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import AuthProvider, User
from app.utils.password import hash_password

router = APIRouter()


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
        password_hash=hash_password(user_data.password),
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
        user.password_hash = hash_password(user_data.password)
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


# =============================================================================
# Update Management Endpoints
# =============================================================================


class UpdateInfo(BaseModel):
    """Available update information."""

    current_version: str
    latest_version: str
    update_available: bool
    release_notes: str | None = None
    release_url: str | None = None
    published_at: datetime | None = None


class UpdateResult(BaseModel):
    """Update operation result."""

    success: bool
    message: str
    previous_version: str | None = None
    new_version: str | None = None
    backup_path: str | None = None


@router.get("/updates/check", response_model=UpdateInfo)
async def check_for_updates(
    admin: Annotated[User, Depends(get_current_active_admin)],
) -> UpdateInfo:
    """Check for available updates from GitHub releases."""
    import httpx
    from app.config import get_settings

    settings = get_settings()
    current_version = settings.app_version

    try:
        # Check GitHub releases API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/repos/eleanor-dfir/eleanor/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
                timeout=10.0,
            )

            if response.status_code == 200:
                release = response.json()
                latest_version = release.get("tag_name", "").lstrip("v")

                # Compare versions (simple string comparison for semver)
                update_available = latest_version > current_version.lstrip("v")

                return UpdateInfo(
                    current_version=current_version,
                    latest_version=latest_version,
                    update_available=update_available,
                    release_notes=release.get("body"),
                    release_url=release.get("html_url"),
                    published_at=release.get("published_at"),
                )
            else:
                # Could not check for updates
                return UpdateInfo(
                    current_version=current_version,
                    latest_version=current_version,
                    update_available=False,
                    release_notes="Could not check for updates",
                )

    except Exception as e:
        return UpdateInfo(
            current_version=current_version,
            latest_version=current_version,
            update_available=False,
            release_notes=f"Error checking for updates: {str(e)}",
        )


@router.post("/updates/apply", response_model=UpdateResult)
async def apply_update(
    admin: Annotated[User, Depends(get_current_active_admin)],
) -> UpdateResult:
    """Apply available update.

    This triggers the update script which:
    1. Creates a backup
    2. Pulls new Docker images
    3. Runs database migrations
    4. Restarts services
    5. Runs health check
    """
    import subprocess
    import os
    from app.config import get_settings

    settings = get_settings()
    current_version = settings.app_version

    update_script = "/opt/eleanor/update.sh"

    if not os.path.exists(update_script):
        return UpdateResult(
            success=False,
            message="Update script not found. Manual update required.",
            previous_version=current_version,
        )

    try:
        # Run update script in background
        result = subprocess.run(
            ["bash", update_script],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd="/opt/eleanor",
        )

        if result.returncode == 0:
            # Get new version (re-read settings)
            from importlib import reload
            from app import config
            reload(config)
            new_settings = config.get_settings()

            return UpdateResult(
                success=True,
                message="Update completed successfully",
                previous_version=current_version,
                new_version=new_settings.app_version,
            )
        else:
            return UpdateResult(
                success=False,
                message=f"Update failed: {result.stderr}",
                previous_version=current_version,
            )

    except subprocess.TimeoutExpired:
        return UpdateResult(
            success=False,
            message="Update timed out after 10 minutes",
            previous_version=current_version,
        )
    except Exception as e:
        return UpdateResult(
            success=False,
            message=f"Update error: {str(e)}",
            previous_version=current_version,
        )


class HealthStatus(BaseModel):
    """System health status."""

    status: str  # healthy, degraded, unhealthy
    components: dict[str, dict]
    timestamp: datetime


@router.get("/health", response_model=HealthStatus)
async def get_system_health(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_active_admin)],
) -> HealthStatus:
    """Get detailed system health status."""
    import asyncio
    from app.database import get_elasticsearch, get_redis

    components = {}
    overall_status = "healthy"

    # Check database
    try:
        await db.execute(select(func.now()))
        components["database"] = {"status": "healthy", "message": "Connected"}
    except Exception as e:
        components["database"] = {"status": "unhealthy", "message": str(e)}
        overall_status = "unhealthy"

    # Check Elasticsearch
    try:
        es = await get_elasticsearch()
        health = await es.cluster.health()
        es_status = health.get("status", "unknown")
        components["elasticsearch"] = {
            "status": "healthy" if es_status == "green" else "degraded",
            "cluster_status": es_status,
            "message": f"Cluster: {health.get('cluster_name')}",
        }
        if es_status == "red":
            overall_status = "unhealthy"
        elif es_status == "yellow" and overall_status == "healthy":
            overall_status = "degraded"
    except Exception as e:
        components["elasticsearch"] = {"status": "unhealthy", "message": str(e)}
        overall_status = "unhealthy"

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        info = await redis.info("memory")
        components["redis"] = {
            "status": "healthy",
            "message": "Connected",
            "used_memory": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        components["redis"] = {"status": "unhealthy", "message": str(e)}
        overall_status = "unhealthy"

    # Check disk space
    import shutil
    try:
        usage = shutil.disk_usage("/var/lib/eleanor")
        free_pct = (usage.free / usage.total) * 100
        disk_status = "healthy" if free_pct > 20 else ("degraded" if free_pct > 10 else "unhealthy")
        components["disk"] = {
            "status": disk_status,
            "message": f"{free_pct:.1f}% free",
            "total_gb": round(usage.total / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
        }
        if disk_status == "unhealthy":
            overall_status = "unhealthy"
        elif disk_status == "degraded" and overall_status == "healthy":
            overall_status = "degraded"
    except Exception as e:
        components["disk"] = {"status": "unknown", "message": str(e)}

    return HealthStatus(
        status=overall_status,
        components=components,
        timestamp=datetime.utcnow(),
    )
