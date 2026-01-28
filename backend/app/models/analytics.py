"""Analytics and detection rules models for Eleanor."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import ArrayType, JSONBType, UUIDType

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class RuleSeverity(str, enum.Enum):
    """Detection rule severity levels."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleStatus(str, enum.Enum):
    """Detection rule status."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    TESTING = "testing"


class RuleType(str, enum.Enum):
    """Detection rule type."""

    SCHEDULED = "scheduled"
    REALTIME = "realtime"
    THRESHOLD = "threshold"
    CORRELATION = "correlation"


class DetectionRule(Base):
    """Detection/analytics rule model."""

    __tablename__ = "detection_rules"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rule configuration
    rule_type: Mapped[RuleType] = mapped_column(
        Enum(RuleType), nullable=False, default=RuleType.SCHEDULED
    )
    severity: Mapped[RuleSeverity] = mapped_column(
        Enum(RuleSeverity), nullable=False, default=RuleSeverity.MEDIUM
    )
    status: Mapped[RuleStatus] = mapped_column(
        Enum(RuleStatus), nullable=False, default=RuleStatus.DISABLED
    )

    # Query configuration
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_language: Mapped[str] = mapped_column(
        String(20), nullable=False, default="kql"
    )  # kql, esql, lucene
    indices: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)

    # Schedule (for scheduled rules)
    schedule_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes
    lookback_period: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes

    # Threshold configuration
    threshold_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    threshold_field: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # MITRE ATT&CK mapping
    mitre_tactics: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    mitre_techniques: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)

    # Tags and categorization
    tags: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_sources: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)

    # Response actions
    auto_create_incident: Mapped[bool] = mapped_column(Boolean, default=False)
    playbook_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Correlation configuration (for correlation rules)
    correlation_config: Mapped[dict | None] = mapped_column(
        JSONBType(), nullable=True
    )  # pattern_type, window, events, join_on, sequence, thresholds

    # Metadata
    custom_fields: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    references: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)

    # Tracking
    created_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Statistics
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    false_positive_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    creator: Mapped["User | None"] = relationship("User")
    executions: Mapped[list["RuleExecution"]] = relationship(
        "RuleExecution", back_populates="rule", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DetectionRule {self.name} ({self.status.value})>"


class RuleExecution(Base):
    """Detection rule execution history."""

    __tablename__ = "rule_executions"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("detection_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Execution details
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Results
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running"
    )  # running, completed, failed
    hits_count: Mapped[int] = mapped_column(Integer, default=0)
    events_scanned: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Incidents created
    incidents_created: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    rule: Mapped["DetectionRule"] = relationship("DetectionRule", back_populates="executions")

    def __repr__(self) -> str:
        return f"<RuleExecution {self.rule_id} at {self.started_at}>"


class CorrelationStateStatus(str, enum.Enum):
    """Correlation state tracking status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class CorrelationState(Base):
    """Tracks partial correlation sequence matches.

    This table stores intermediate state for correlation rules that
    require tracking event sequences across time windows.
    """

    __tablename__ = "correlation_states"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("detection_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Entity key for grouping (e.g., "user.name:admin" or "host.name:server01")
    entity_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    # Current state of the correlation sequence
    state: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    # State structure:
    # {
    #   "matched_events": [{"event_id": "...", "step": "failed_logins", "timestamp": "..."}],
    #   "current_step": 0,
    #   "counts": {"failed_logins": 5, "success": 0},
    #   "first_event_id": "...",
    # }

    # Time window tracking
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Status
    status: Mapped[CorrelationStateStatus] = mapped_column(
        Enum(CorrelationStateStatus),
        nullable=False,
        default=CorrelationStateStatus.ACTIVE,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    rule: Mapped["DetectionRule"] = relationship("DetectionRule")

    def __repr__(self) -> str:
        return f"<CorrelationState {self.rule_id}:{self.entity_key} ({self.status.value})>"
