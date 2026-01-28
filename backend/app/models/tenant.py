"""Tenant models for multi-tenancy support in Eleanor."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import JSONBType, UUIDType

if TYPE_CHECKING:
    from app.models.user import User


class TenantStatus(str, enum.Enum):
    """Tenant status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


class TenantPlan(str, enum.Enum):
    """Tenant subscription plan."""

    FREE = "free"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Tenant(Base):
    """Organization/tenant model for multi-tenancy."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )  # Used for ES index naming: eleanor-{slug}-events-*
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status and plan
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus), nullable=False, default=TenantStatus.ACTIVE
    )
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan), nullable=False, default=TenantPlan.FREE
    )

    # Contact information
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Settings and limits
    settings: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    # Settings structure:
    # {
    #   "max_users": 10,
    #   "max_cases": 100,
    #   "max_evidence_gb": 50,
    #   "retention_days": 365,
    #   "features": ["correlation", "playbooks", "mitre"],
    #   "branding": {"logo_url": "...", "primary_color": "#..."},
    # }

    # Domain for SSO routing (optional)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    members: Mapped[list["TenantMembership"]] = relationship(
        "TenantMembership", back_populates="tenant", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["TenantAPIKey"]] = relationship(
        "TenantAPIKey", back_populates="tenant", cascade="all, delete-orphan"
    )
    adapter_configs: Mapped[list["TenantAdapterConfig"]] = relationship(
        "TenantAdapterConfig", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}: {self.name}>"

    @property
    def elasticsearch_prefix(self) -> str:
        """Get Elasticsearch index prefix for this tenant."""
        return f"eleanor-{self.slug}"

    def has_feature(self, feature: str) -> bool:
        """Check if tenant has access to a specific feature."""
        features = self.settings.get("features", [])
        return feature in features


class TenantMembershipRole(str, enum.Enum):
    """Tenant membership roles."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class TenantMembership(Base):
    """User membership in a tenant."""

    __tablename__ = "tenant_memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_tenant_user"),)

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Role within the tenant
    role: Mapped[TenantMembershipRole] = mapped_column(
        Enum(TenantMembershipRole),
        nullable=False,
        default=TenantMembershipRole.MEMBER,
    )

    # Is this the user's default tenant?
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="tenant_memberships")

    def __repr__(self) -> str:
        return f"<TenantMembership {self.tenant_id}:{self.user_id} ({self.role.value})>"


class TenantAPIKey(Base):
    """API key for tenant authentication."""

    __tablename__ = "tenant_api_keys"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # API key details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # First 8 chars for identification
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt hash

    # Permissions and scopes
    scopes: Mapped[list[str]] = mapped_column(
        JSONBType(), default=list
    )  # ["read:events", "write:alerts", ...]

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<TenantAPIKey {self.key_prefix}... ({self.name})>"


class TenantAdapterConfig(Base):
    """Per-tenant external system configuration."""

    __tablename__ = "tenant_adapter_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "adapter_type", name="uq_tenant_adapter"),)

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Adapter identification
    adapter_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # velociraptor, shuffle, iris, etc.

    # Configuration (encrypted sensitive values stored separately)
    config: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    # Config structure varies by adapter type:
    # {
    #   "url": "https://...",
    #   "verify_ssl": true,
    #   "custom_headers": {...},
    # }

    # Encrypted credentials (stored separately for security)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    health_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # healthy, unhealthy, unknown

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="adapter_configs")

    def __repr__(self) -> str:
        return f"<TenantAdapterConfig {self.tenant_id}:{self.adapter_type}>"
