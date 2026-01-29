"""Tenant management API endpoints.

All endpoints require admin authentication since tenant management
is a privileged operation.
"""

import hashlib
import logging
import re
import secrets
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.v1.auth import get_current_active_admin
from app.database import get_db
from app.models.tenant import (
    Tenant,
    TenantAdapterConfig,
    TenantAPIKey,
    TenantMembership,
    TenantMembershipRole,
    TenantPlan,
    TenantStatus,
)
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class TenantCreate(BaseModel):
    """Schema for creating a new tenant."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    contact_email: str | None = None
    contact_name: str | None = None
    plan: TenantPlan = TenantPlan.FREE
    domain: str | None = None
    settings: dict = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format."""
        v = v.lower().strip()
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError(
                "Slug must start with a letter, contain only lowercase letters, "
                "numbers, and hyphens, and end with a letter or number"
            )
        if len(v) < 2:
            raise ValueError("Slug must be at least 2 characters")
        return v


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""

    name: str | None = None
    description: str | None = None
    contact_email: str | None = None
    contact_name: str | None = None
    status: TenantStatus | None = None
    plan: TenantPlan | None = None
    domain: str | None = None
    settings: dict | None = None


class TenantResponse(BaseModel):
    """Schema for tenant response."""

    id: UUID
    name: str
    slug: str
    description: str | None
    status: TenantStatus
    plan: TenantPlan
    contact_email: str | None
    contact_name: str | None
    domain: str | None
    settings: dict
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

    class Config:
        from_attributes = True


class TenantMembershipCreate(BaseModel):
    """Schema for adding a user to a tenant."""

    user_id: UUID
    role: TenantMembershipRole = TenantMembershipRole.MEMBER
    is_default: bool = False


class TenantMembershipUpdate(BaseModel):
    """Schema for updating a membership."""

    role: TenantMembershipRole | None = None
    is_default: bool | None = None


class TenantMembershipResponse(BaseModel):
    """Schema for membership response."""

    id: UUID
    tenant_id: UUID
    user_id: UUID
    role: TenantMembershipRole
    is_default: bool
    joined_at: datetime
    user_email: str | None = None
    user_display_name: str | None = None

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class APIKeyResponse(BaseModel):
    """Schema for API key response (without the full key)."""

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(APIKeyResponse):
    """Schema for newly created API key (includes the full key once)."""

    key: str  # Full API key, only shown once at creation


class AdapterConfigCreate(BaseModel):
    """Schema for creating adapter configuration."""

    adapter_type: str
    config: dict = Field(default_factory=dict)
    is_enabled: bool = True


class AdapterConfigUpdate(BaseModel):
    """Schema for updating adapter configuration."""

    config: dict | None = None
    is_enabled: bool | None = None


class AdapterConfigResponse(BaseModel):
    """Schema for adapter config response."""

    id: UUID
    adapter_type: str
    config: dict
    is_enabled: bool
    health_status: str | None
    last_health_check: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Tenant CRUD Endpoints
# =============================================================================


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> Tenant:
    """Create a new tenant organization.

    Requires admin authentication.
    """
    # Check if slug already exists
    existing = await db.execute(select(Tenant).where(Tenant.slug == tenant_data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{tenant_data.slug}' already exists",
        )

    # Check if domain already exists
    if tenant_data.domain:
        existing_domain = await db.execute(
            select(Tenant).where(Tenant.domain == tenant_data.domain.lower())
        )
        if existing_domain.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant with domain '{tenant_data.domain}' already exists",
            )

    # Create tenant with default features
    default_settings = {
        "max_users": 10,
        "max_cases": 100,
        "max_evidence_gb": 50,
        "retention_days": 365,
        "features": ["correlation", "playbooks", "mitre", "realtime"],
    }
    default_settings.update(tenant_data.settings)

    tenant = Tenant(
        name=tenant_data.name,
        slug=tenant_data.slug.lower(),
        description=tenant_data.description,
        contact_email=tenant_data.contact_email,
        contact_name=tenant_data.contact_name,
        plan=tenant_data.plan,
        domain=tenant_data.domain.lower() if tenant_data.domain else None,
        settings=default_settings,
    )

    db.add(tenant)
    await db.flush()

    logger.info("Created tenant: %s (%s)", tenant.name, tenant.slug)
    return tenant


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
    status_filter: TenantStatus | None = Query(None, alias="status"),
    plan: TenantPlan | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[Tenant]:
    """List all tenants.

    Requires admin authentication.
    """
    query = select(Tenant)

    if status_filter:
        query = query.where(Tenant.status == status_filter)
    if plan:
        query = query.where(Tenant.plan == plan)
    if search:
        query = query.where((Tenant.name.ilike(f"%{search}%")) | (Tenant.slug.ilike(f"%{search}%")))

    query = query.order_by(Tenant.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    tenants = result.scalars().all()

    # Get member counts
    for tenant in tenants:
        count_query = select(func.count(TenantMembership.id)).where(
            TenantMembership.tenant_id == tenant.id
        )
        count_result = await db.execute(count_query)
        tenant.member_count = count_result.scalar() or 0

    return list(tenants)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> Tenant:
    """Get tenant details.

    Requires admin authentication.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Get member count
    count_query = select(func.count(TenantMembership.id)).where(
        TenantMembership.tenant_id == tenant.id
    )
    count_result = await db.execute(count_query)
    tenant.member_count = count_result.scalar() or 0

    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> Tenant:
    """Update tenant details.

    Requires admin authentication.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Update fields
    update_data = tenant_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "domain" and value:
            value = value.lower()
        setattr(tenant, field, value)

    logger.info("Updated tenant: %s", tenant.slug)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> None:
    """Delete a tenant (soft delete - sets status to suspended).

    Requires admin authentication.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Soft delete - set to suspended
    tenant.status = TenantStatus.SUSPENDED
    logger.info("Suspended tenant: %s", tenant.slug)


# =============================================================================
# Membership Endpoints
# =============================================================================


@router.get("/{tenant_id}/members", response_model=list[TenantMembershipResponse])
async def list_tenant_members(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> list[TenantMembership]:
    """List all members of a tenant.

    Requires admin authentication.
    """
    query = (
        select(TenantMembership)
        .options(joinedload(TenantMembership.user))
        .where(TenantMembership.tenant_id == tenant_id)
        .order_by(TenantMembership.joined_at.desc())
    )

    result = await db.execute(query)
    memberships = result.scalars().all()

    # Enrich with user info
    for membership in memberships:
        if membership.user:
            membership.user_email = membership.user.email
            membership.user_display_name = membership.user.display_name

    return list(memberships)


@router.post(
    "/{tenant_id}/members",
    response_model=TenantMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_tenant_member(
    tenant_id: UUID,
    membership_data: TenantMembershipCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> TenantMembership:
    """Add a user to a tenant.

    Requires admin authentication.
    """
    # Verify tenant exists
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == membership_data.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if membership already exists
    existing = await db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == membership_data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this tenant",
        )

    # If setting as default, unset other defaults for this user
    if membership_data.is_default:
        await db.execute(
            select(TenantMembership)
            .where(
                TenantMembership.user_id == membership_data.user_id,
                TenantMembership.is_default == True,  # noqa: E712
            )
            .with_for_update()
        )
        # This just acquires locks, actual update below
        from sqlalchemy import update

        await db.execute(
            update(TenantMembership)
            .where(
                TenantMembership.user_id == membership_data.user_id,
                TenantMembership.is_default == True,  # noqa: E712
            )
            .values(is_default=False)
        )

    membership = TenantMembership(
        tenant_id=tenant_id,
        user_id=membership_data.user_id,
        role=membership_data.role,
        is_default=membership_data.is_default,
    )

    db.add(membership)
    await db.flush()

    membership.user_email = user.email
    membership.user_display_name = user.display_name

    logger.info(
        "Added user %s to tenant %s with role %s",
        membership_data.user_id,
        tenant_id,
        membership_data.role.value,
    )
    return membership


@router.patch(
    "/{tenant_id}/members/{user_id}",
    response_model=TenantMembershipResponse,
)
async def update_tenant_member(
    tenant_id: UUID,
    user_id: UUID,
    membership_data: TenantMembershipUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> TenantMembership:
    """Update a tenant membership.

    Requires admin authentication.
    """
    query = (
        select(TenantMembership)
        .options(joinedload(TenantMembership.user))
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    result = await db.execute(query)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    # Update fields
    if membership_data.role is not None:
        membership.role = membership_data.role

    if membership_data.is_default is not None:
        if membership_data.is_default:
            # Unset other defaults for this user
            from sqlalchemy import update

            await db.execute(
                update(TenantMembership)
                .where(
                    TenantMembership.user_id == user_id,
                    TenantMembership.is_default == True,  # noqa: E712
                    TenantMembership.id != membership.id,
                )
                .values(is_default=False)
            )
        membership.is_default = membership_data.is_default

    membership.user_email = membership.user.email if membership.user else None
    membership.user_display_name = membership.user.display_name if membership.user else None

    return membership


@router.delete(
    "/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_tenant_member(
    tenant_id: UUID,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> None:
    """Remove a user from a tenant.

    Requires admin authentication.
    """
    result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    await db.delete(membership)
    logger.info("Removed user %s from tenant %s", user_id, tenant_id)


# =============================================================================
# API Key Endpoints
# =============================================================================


@router.get("/{tenant_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> list[TenantAPIKey]:
    """List all API keys for a tenant.

    Requires admin authentication.
    """
    query = (
        select(TenantAPIKey)
        .where(TenantAPIKey.tenant_id == tenant_id)
        .order_by(TenantAPIKey.created_at.desc())
    )

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/{tenant_id}/api-keys",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    tenant_id: UUID,
    key_data: APIKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> dict:
    """Create a new API key for a tenant.

    Requires admin authentication.
    The full API key is only returned once at creation time.
    """
    # Verify tenant exists
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Generate API key
    key = secrets.token_urlsafe(32)
    key_prefix = key[:8]
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    api_key = TenantAPIKey(
        tenant_id=tenant_id,
        name=key_data.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=key_data.scopes,
        expires_at=key_data.expires_at,
    )

    db.add(api_key)
    await db.flush()

    logger.info(
        "Created API key '%s' for tenant %s (prefix: %s)",
        key_data.name,
        tenant_id,
        key_prefix,
    )

    # Return full key only at creation
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": key,  # Full key, shown only once
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active,
        "expires_at": api_key.expires_at,
        "last_used_at": api_key.last_used_at,
        "created_at": api_key.created_at,
    }


@router.delete(
    "/{tenant_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    tenant_id: UUID,
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> None:
    """Revoke an API key.

    Requires admin authentication.
    """
    result = await db.execute(
        select(TenantAPIKey).where(
            TenantAPIKey.id == key_id,
            TenantAPIKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key.is_active = False
    logger.info("Revoked API key %s for tenant %s", key_id, tenant_id)


# =============================================================================
# Adapter Configuration Endpoints
# =============================================================================


@router.get("/{tenant_id}/adapters", response_model=list[AdapterConfigResponse])
async def list_adapter_configs(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> list[TenantAdapterConfig]:
    """List all adapter configurations for a tenant.

    Requires admin authentication.
    """
    query = (
        select(TenantAdapterConfig)
        .where(TenantAdapterConfig.tenant_id == tenant_id)
        .order_by(TenantAdapterConfig.adapter_type)
    )

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/{tenant_id}/adapters",
    response_model=AdapterConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_adapter_config(
    tenant_id: UUID,
    config_data: AdapterConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> TenantAdapterConfig:
    """Create adapter configuration for a tenant.

    Requires admin authentication.
    """
    # Verify tenant exists
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Check if adapter config already exists
    existing = await db.execute(
        select(TenantAdapterConfig).where(
            TenantAdapterConfig.tenant_id == tenant_id,
            TenantAdapterConfig.adapter_type == config_data.adapter_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration for adapter '{config_data.adapter_type}' already exists",
        )

    config = TenantAdapterConfig(
        tenant_id=tenant_id,
        adapter_type=config_data.adapter_type,
        config=config_data.config,
        is_enabled=config_data.is_enabled,
    )

    db.add(config)
    await db.flush()

    logger.info(
        "Created adapter config '%s' for tenant %s",
        config_data.adapter_type,
        tenant_id,
    )
    return config


@router.patch(
    "/{tenant_id}/adapters/{adapter_type}",
    response_model=AdapterConfigResponse,
)
async def update_adapter_config(
    tenant_id: UUID,
    adapter_type: str,
    config_data: AdapterConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> TenantAdapterConfig:
    """Update adapter configuration.

    Requires admin authentication.
    """
    result = await db.execute(
        select(TenantAdapterConfig).where(
            TenantAdapterConfig.tenant_id == tenant_id,
            TenantAdapterConfig.adapter_type == adapter_type,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adapter configuration not found",
        )

    if config_data.config is not None:
        config.config = config_data.config
    if config_data.is_enabled is not None:
        config.is_enabled = config_data.is_enabled

    return config


@router.delete(
    "/{tenant_id}/adapters/{adapter_type}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_adapter_config(
    tenant_id: UUID,
    adapter_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_admin)],
) -> None:
    """Delete adapter configuration.

    Requires admin authentication.
    """
    result = await db.execute(
        select(TenantAdapterConfig).where(
            TenantAdapterConfig.tenant_id == tenant_id,
            TenantAdapterConfig.adapter_type == adapter_type,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adapter configuration not found",
        )

    await db.delete(config)
    logger.info("Deleted adapter config '%s' for tenant %s", adapter_type, tenant_id)
