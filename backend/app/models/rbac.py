"""Role-Based Access Control models for Eleanor."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import UUIDType

# Many-to-many association table for Role-Permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUIDType(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUIDType(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many association table for User-Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUIDType(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class PermissionScope(str, Enum):
    """Permission scope categories."""

    CASES = "cases"
    EVIDENCE = "evidence"
    SEARCH = "search"
    ENTITIES = "entities"
    ENRICHMENT = "enrichment"
    COLLECTION = "collection"
    WORKFLOWS = "workflows"
    INTEGRATIONS = "integrations"
    ANALYTICS = "analytics"
    CONNECTORS = "connectors"
    USERS = "users"
    ADMIN = "admin"


class PermissionAction(str, Enum):
    """Permission actions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    MANAGE = "manage"


class Permission(Base):
    """Permission model for granular access control."""

    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    scope: Mapped[PermissionScope] = mapped_column(String(50), nullable=False)
    action: Mapped[PermissionAction] = mapped_column(String(50), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(100))  # Optional specific resource

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint("scope", "action", "resource", name="uq_permission_scope_action_resource"),
    )


class Role(Base):
    """Role model for grouping permissions."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_system: Mapped[bool] = mapped_column(default=False)  # Built-in roles cannot be deleted
    priority: Mapped[int] = mapped_column(default=0)  # Higher priority roles override lower ones
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    permissions: Mapped[list[Permission]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles"
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="role_objects"
    )


# Default roles and permissions
DEFAULT_ROLES = [
    {
        "name": "admin",
        "description": "Full system administrator with all permissions",
        "is_system": True,
        "priority": 100,
        "permissions": ["*"]  # All permissions
    },
    {
        "name": "analyst",
        "description": "Security analyst with investigation capabilities",
        "is_system": True,
        "priority": 50,
        "permissions": [
            "cases:read", "cases:create", "cases:update",
            "evidence:read", "evidence:create",
            "search:read", "search:execute",
            "entities:read",
            "enrichment:read", "enrichment:execute",
            "workflows:read", "workflows:execute",
            "analytics:read",
        ]
    },
    {
        "name": "investigator",
        "description": "Lead investigator with case management permissions",
        "is_system": True,
        "priority": 60,
        "permissions": [
            "cases:read", "cases:create", "cases:update", "cases:delete",
            "evidence:read", "evidence:create", "evidence:update", "evidence:delete",
            "search:read", "search:execute",
            "entities:read", "entities:update",
            "enrichment:read", "enrichment:execute",
            "collection:read", "collection:execute",
            "workflows:read", "workflows:execute", "workflows:approve",
            "analytics:read", "analytics:create",
        ]
    },
    {
        "name": "viewer",
        "description": "Read-only access to cases and evidence",
        "is_system": True,
        "priority": 10,
        "permissions": [
            "cases:read",
            "evidence:read",
            "search:read",
            "entities:read",
            "analytics:read",
        ]
    },
    {
        "name": "collector",
        "description": "Evidence collection specialist",
        "is_system": True,
        "priority": 40,
        "permissions": [
            "cases:read",
            "evidence:read", "evidence:create", "evidence:update",
            "collection:read", "collection:execute",
            "entities:read",
        ]
    },
]

DEFAULT_PERMISSIONS = [
    # Cases
    {"name": "cases:create", "scope": "cases", "action": "create", "description": "Create new cases"},
    {"name": "cases:read", "scope": "cases", "action": "read", "description": "View cases"},
    {"name": "cases:update", "scope": "cases", "action": "update", "description": "Update cases"},
    {"name": "cases:delete", "scope": "cases", "action": "delete", "description": "Delete cases"},

    # Evidence
    {"name": "evidence:create", "scope": "evidence", "action": "create", "description": "Upload evidence"},
    {"name": "evidence:read", "scope": "evidence", "action": "read", "description": "View evidence"},
    {"name": "evidence:update", "scope": "evidence", "action": "update", "description": "Update evidence"},
    {"name": "evidence:delete", "scope": "evidence", "action": "delete", "description": "Delete evidence"},

    # Search
    {"name": "search:read", "scope": "search", "action": "read", "description": "View saved queries"},
    {"name": "search:execute", "scope": "search", "action": "execute", "description": "Execute searches"},
    {"name": "search:manage", "scope": "search", "action": "manage", "description": "Manage saved queries"},

    # Entities
    {"name": "entities:read", "scope": "entities", "action": "read", "description": "View entities"},
    {"name": "entities:update", "scope": "entities", "action": "update", "description": "Update entity tags"},

    # Enrichment
    {"name": "enrichment:read", "scope": "enrichment", "action": "read", "description": "View enrichment data"},
    {"name": "enrichment:execute", "scope": "enrichment", "action": "execute", "description": "Run enrichments"},

    # Collection
    {"name": "collection:read", "scope": "collection", "action": "read", "description": "View collection jobs"},
    {"name": "collection:execute", "scope": "collection", "action": "execute", "description": "Start collections"},
    {"name": "collection:manage", "scope": "collection", "action": "manage", "description": "Manage endpoints"},

    # Workflows
    {"name": "workflows:read", "scope": "workflows", "action": "read", "description": "View workflows"},
    {"name": "workflows:execute", "scope": "workflows", "action": "execute", "description": "Trigger workflows"},
    {"name": "workflows:approve", "scope": "workflows", "action": "approve", "description": "Approve workflow actions"},
    {"name": "workflows:manage", "scope": "workflows", "action": "manage", "description": "Manage workflow definitions"},

    # Integrations
    {"name": "integrations:read", "scope": "integrations", "action": "read", "description": "View integrations"},
    {"name": "integrations:manage", "scope": "integrations", "action": "manage", "description": "Manage integrations"},

    # Analytics
    {"name": "analytics:read", "scope": "analytics", "action": "read", "description": "View detection rules"},
    {"name": "analytics:create", "scope": "analytics", "action": "create", "description": "Create detection rules"},
    {"name": "analytics:manage", "scope": "analytics", "action": "manage", "description": "Manage detection rules"},

    # Connectors
    {"name": "connectors:read", "scope": "connectors", "action": "read", "description": "View data connectors"},
    {"name": "connectors:manage", "scope": "connectors", "action": "manage", "description": "Manage data connectors"},

    # Users
    {"name": "users:read", "scope": "users", "action": "read", "description": "View users"},
    {"name": "users:manage", "scope": "users", "action": "manage", "description": "Manage users"},

    # Admin
    {"name": "admin:manage", "scope": "admin", "action": "manage", "description": "Full admin access"},
]


def get_permission_string(scope: PermissionScope, action: PermissionAction, resource: str | None = None) -> str:
    """Generate permission string from components."""
    if resource:
        return f"{scope.value}:{action.value}:{resource}"
    return f"{scope.value}:{action.value}"


def parse_permission_string(perm: str) -> tuple[str, str, str | None]:
    """Parse permission string into components."""
    parts = perm.split(":")
    if len(parts) == 2:
        return parts[0], parts[1], None
    elif len(parts) == 3:
        return parts[0], parts[1], parts[2]
    raise ValueError(f"Invalid permission string: {perm}")
