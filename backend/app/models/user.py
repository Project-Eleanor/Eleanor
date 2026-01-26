"""User model for Eleanor."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import ArrayType, UUIDType

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.rbac import Role


class AuthProvider(str, enum.Enum):
    """Authentication provider types."""

    OIDC = "oidc"
    LDAP = "ldap"
    SAM = "sam"


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider), nullable=False, default=AuthProvider.SAM
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    roles: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    assigned_cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="assignee", foreign_keys="Case.assignee_id"
    )
    created_cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="created_by_user", foreign_keys="Case.created_by"
    )
    role_objects: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Admins have all permissions
        if self.is_admin:
            return True

        # Check role-based permissions
        for role in self.role_objects:
            for perm in role.permissions:
                # Wildcard permission
                if perm.name == "*":
                    return True
                # Exact match
                if perm.name == permission:
                    return True
                # Scope wildcard (e.g., "cases:*" matches "cases:read")
                if perm.name.endswith(":*"):
                    scope = perm.name[:-2]
                    if permission.startswith(f"{scope}:"):
                        return True

        return False

    def get_permissions(self) -> set[str]:
        """Get all permissions for this user."""
        if self.is_admin:
            return {"*"}

        permissions = set()
        for role in self.role_objects:
            for perm in role.permissions:
                permissions.add(perm.name)

        return permissions
