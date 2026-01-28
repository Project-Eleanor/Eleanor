"""Case model for Eleanor."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import ArrayType, JSONBType, UUIDType

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.tenant import Tenant
    from app.models.user import User


class Severity(str, enum.Enum):
    """Case severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class Priority(str, enum.Enum):
    """Case priority levels."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class CaseStatus(str, enum.Enum):
    """Case lifecycle status."""

    NEW = "new"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    ERADICATED = "eradicated"
    RECOVERED = "recovered"
    CLOSED = "closed"


class Case(Base):
    """Investigation case model."""

    __tablename__ = "cases"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity), nullable=False, default=Severity.MEDIUM
    )
    priority: Mapped[Priority] = mapped_column(Enum(Priority), nullable=False, default=Priority.P3)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus), nullable=False, default=CaseStatus.NEW
    )

    # Foreign keys
    assignee_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tags and MITRE
    tags: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    mitre_tactics: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    mitre_techniques: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)

    # Additional metadata (named case_metadata to avoid conflict with SQLAlchemy Base.metadata)
    case_metadata: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    assignee: Mapped["User | None"] = relationship(
        "User", back_populates="assigned_cases", foreign_keys=[assignee_id]
    )
    created_by_user: Mapped["User | None"] = relationship(
        "User", back_populates="created_cases", foreign_keys=[created_by]
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Case {self.case_number}: {self.title}>"
