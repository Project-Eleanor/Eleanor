"""RBAC (Role-Based Access Control) API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.exceptions import AuthorizationError, BadRequestError, NotFoundError
from app.models.rbac import Permission, Role
from app.models.user import User

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class PermissionResponse(BaseModel):
    """Permission response."""

    id: UUID
    name: str
    description: str | None
    scope: str
    action: str
    resource: str | None

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    """Role creation request."""

    name: str
    description: str | None = None
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    """Role update request."""

    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    """Role response."""

    id: UUID
    name: str
    description: str | None
    is_system: bool
    priority: int
    permissions: list[PermissionResponse]

    class Config:
        from_attributes = True


class UserRoleAssignment(BaseModel):
    """User role assignment request."""

    role_ids: list[UUID]


class UserPermissionsResponse(BaseModel):
    """User permissions response."""

    user_id: UUID
    username: str
    is_admin: bool
    roles: list[str]
    permissions: list[str]


# =============================================================================
# Permission Endpoints
# =============================================================================


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: str | None = Query(None),
) -> list[PermissionResponse]:
    """List all permissions."""
    query = select(Permission)

    if scope:
        query = query.where(Permission.scope == scope)

    query = query.order_by(Permission.scope, Permission.action)
    result = await db.execute(query)
    permissions = result.scalars().all()

    return [PermissionResponse.model_validate(p) for p in permissions]


# =============================================================================
# Role Endpoints
# =============================================================================


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[RoleResponse]:
    """List all roles."""
    query = (
        select(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.priority.desc(), Role.name)
    )
    result = await db.execute(query)
    roles = result.scalars().all()

    return [
        RoleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            priority=r.priority,
            permissions=[PermissionResponse.model_validate(p) for p in r.permissions],
        )
        for r in roles
    ]


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RoleResponse:
    """Get a role by ID."""
    query = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    result = await db.execute(query)
    role = result.scalar_one_or_none()

    if not role:
        raise NotFoundError("Role", str(role_id))

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        priority=role.priority,
        permissions=[PermissionResponse.model_validate(p) for p in role.permissions],
    )


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RoleResponse:
    """Create a new role."""
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required to create roles")

    # Check for duplicate name
    existing = await db.execute(select(Role).where(Role.name == role_data.name))
    if existing.scalar_one_or_none():
        raise BadRequestError(f"Role '{role_data.name}' already exists")

    # Get permissions
    permissions = []
    if role_data.permissions:
        perm_query = select(Permission).where(Permission.name.in_(role_data.permissions))
        perm_result = await db.execute(perm_query)
        permissions = list(perm_result.scalars().all())

    role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=permissions,
    )

    db.add(role)
    await db.commit()
    await db.refresh(role)

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        priority=role.priority,
        permissions=[PermissionResponse.model_validate(p) for p in role.permissions],
    )


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RoleResponse:
    """Update a role."""
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required to update roles")

    query = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    result = await db.execute(query)
    role = result.scalar_one_or_none()

    if not role:
        raise NotFoundError("Role", str(role_id))

    if role.is_system and role_data.name and role_data.name != role.name:
        raise BadRequestError("Cannot rename system roles")

    if role_data.name:
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.permissions is not None:
        perm_query = select(Permission).where(Permission.name.in_(role_data.permissions))
        perm_result = await db.execute(perm_query)
        role.permissions = list(perm_result.scalars().all())

    await db.commit()
    await db.refresh(role)

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        priority=role.priority,
        permissions=[PermissionResponse.model_validate(p) for p in role.permissions],
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a role."""
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required to delete roles")

    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if not role:
        raise NotFoundError("Role", str(role_id))

    if role.is_system:
        raise BadRequestError("Cannot delete system roles")

    await db.delete(role)
    await db.commit()


# =============================================================================
# User Role Assignment Endpoints
# =============================================================================


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
async def get_user_permissions(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPermissionsResponse:
    """Get permissions for a specific user."""
    query = (
        select(User)
        .options(selectinload(User.role_objects).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    permissions = user.get_permissions()
    role_names = [r.name for r in user.role_objects]

    return UserPermissionsResponse(
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        roles=role_names,
        permissions=sorted(permissions),
    )


@router.get("/users/me/permissions", response_model=UserPermissionsResponse)
async def get_my_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPermissionsResponse:
    """Get permissions for the current user."""
    # Refresh user with roles loaded
    query = (
        select(User)
        .options(selectinload(User.role_objects).selectinload(Role.permissions))
        .where(User.id == current_user.id)
    )
    result = await db.execute(query)
    user = result.scalar_one()

    permissions = user.get_permissions()
    role_names = [r.name for r in user.role_objects]

    return UserPermissionsResponse(
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        roles=role_names,
        permissions=sorted(permissions),
    )


@router.put("/users/{user_id}/roles", response_model=UserPermissionsResponse)
async def assign_user_roles(
    user_id: UUID,
    assignment: UserRoleAssignment,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPermissionsResponse:
    """Assign roles to a user."""
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required to assign roles")

    query = (
        select(User)
        .options(selectinload(User.role_objects).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    # Get roles to assign
    roles_query = select(Role).where(Role.id.in_(assignment.role_ids))
    roles_result = await db.execute(roles_query)
    roles = list(roles_result.scalars().all())

    user.role_objects = roles
    await db.commit()
    await db.refresh(user)

    permissions = user.get_permissions()
    role_names = [r.name for r in user.role_objects]

    return UserPermissionsResponse(
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        roles=role_names,
        permissions=sorted(permissions),
    )


# =============================================================================
# Permission Check Helper
# =============================================================================


def require_permission(permission: str):
    """Dependency to require a specific permission."""

    async def check_permission(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        # Load user with roles
        query = (
            select(User)
            .options(selectinload(User.role_objects).selectinload(Role.permissions))
            .where(User.id == current_user.id)
        )
        result = await db.execute(query)
        user = result.scalar_one()

        if not user.has_permission(permission):
            raise AuthorizationError(f"Permission '{permission}' required")

        return user

    return check_permission
