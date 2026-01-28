"""Alert model for Eleanor detection system.

Alerts are created when detection rules match events. They track:
- Rule that triggered the alert
- Matched events and entities
- Alert lifecycle (open -> acknowledged -> closed)
- Case association
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import ArrayType, JSONBType, UUIDType

if TYPE_CHECKING:
    from app.models.analytics import DetectionRule
    from app.models.case import Case
    from app.models.user import User


class AlertSeverity(str, enum.Enum):
    """Alert severity levels."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    """Alert status lifecycle."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    SUPPRESSED = "suppressed"


class Alert(Base):
    """Security alert generated from detection rules."""

    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)

    # Rule reference
    rule_id: Mapped[UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("detection_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Alert details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity), nullable=False, default=AlertSeverity.MEDIUM
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), nullable=False, default=AlertStatus.OPEN, index=True
    )

    # Occurrence tracking
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # MITRE ATT&CK
    mitre_tactics: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    mitre_techniques: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)

    # Classification
    tags: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)

    # Events and entities (stored as JSON for flexibility)
    events: Mapped[list[dict]] = mapped_column(JSONBType(), default=list)
    entities: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # Case association
    case_id: Mapped[UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Workflow tracking
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_false_positive: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    rule: Mapped["DetectionRule | None"] = relationship("DetectionRule", foreign_keys=[rule_id])
    case: Mapped["Case | None"] = relationship("Case", foreign_keys=[case_id])
    acknowledger: Mapped["User | None"] = relationship("User", foreign_keys=[acknowledged_by])
    closer: Mapped["User | None"] = relationship("User", foreign_keys=[closed_by])

    def __repr__(self) -> str:
        return f"<Alert {self.title} ({self.status.value})>"
