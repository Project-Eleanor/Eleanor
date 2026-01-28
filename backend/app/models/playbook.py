"""Playbook models for response automation in Eleanor."""

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
    from app.models.tenant import Tenant
    from app.models.user import User


class PlaybookStatus(str, enum.Enum):
    """Playbook status."""

    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class StepType(str, enum.Enum):
    """Playbook step types."""

    ACTION = "action"  # Execute an action
    CONDITION = "condition"  # Branching logic
    APPROVAL = "approval"  # Require human approval
    DELAY = "delay"  # Wait for duration
    PARALLEL = "parallel"  # Execute steps in parallel
    LOOP = "loop"  # Iterate over items
    NOTIFICATION = "notification"  # Send notification
    SOAR = "soar"  # Execute SOAR workflow


class ExecutionStatus(str, enum.Enum):
    """Execution status."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ApprovalStatus(str, enum.Enum):
    """Approval status."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class Playbook(Base):
    """Playbook definition model."""

    __tablename__ = "playbooks"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Status
    status: Mapped[PlaybookStatus] = mapped_column(
        Enum(PlaybookStatus), nullable=False, default=PlaybookStatus.DRAFT
    )

    # Configuration
    steps: Mapped[list[dict]] = mapped_column(JSONBType(), default=list)
    # Steps structure:
    # [
    #   {
    #     "id": "step_1",
    #     "name": "Block IP",
    #     "type": "action",
    #     "action": "block_ip",
    #     "parameters": {"ip": "{{ alert.source_ip }}"},
    #     "on_success": "step_2",
    #     "on_failure": "step_error",
    #     "timeout_seconds": 60,
    #   },
    #   {
    #     "id": "step_2",
    #     "name": "Require Approval",
    #     "type": "approval",
    #     "approvers": ["admin"],
    #     "timeout_hours": 4,
    #     "on_approve": "step_3",
    #     "on_deny": "step_end",
    #   },
    #   ...
    # ]

    # Trigger configuration
    trigger_on_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger_on_incident: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger_conditions: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    # Trigger conditions:
    # {
    #   "severity": ["high", "critical"],
    #   "tags": ["ransomware", "malware"],
    #   "mitre_techniques": ["T1486"],
    # }

    # Input/Output schema
    input_schema: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    output_schema: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # Settings
    settings: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    # Settings:
    # {
    #   "max_parallel_executions": 5,
    #   "default_timeout_seconds": 3600,
    #   "retry_on_failure": true,
    #   "max_retries": 3,
    # }

    # Tags and categorization
    tags: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Statistics
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    creator: Mapped["User | None"] = relationship("User")
    executions: Mapped[list["PlaybookExecution"]] = relationship(
        "PlaybookExecution", back_populates="playbook", cascade="all, delete-orphan"
    )
    rule_bindings: Mapped[list["RulePlaybookBinding"]] = relationship(
        "RulePlaybookBinding", back_populates="playbook", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Playbook {self.name} ({self.status.value})>"


class PlaybookExecution(Base):
    """Playbook execution tracking."""

    __tablename__ = "playbook_executions"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    playbook_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("playbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Execution state
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), nullable=False, default=ExecutionStatus.PENDING
    )
    current_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Trigger context
    trigger_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # alert, incident, manual
    trigger_id: Mapped[UUID | None] = mapped_column(UUIDType(), nullable=True)  # Alert/Incident ID

    # Input/Output
    input_data: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    output_data: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # Step results
    step_results: Mapped[list[dict]] = mapped_column(JSONBType(), default=list)
    # Step results:
    # [
    #   {
    #     "step_id": "step_1",
    #     "status": "completed",
    #     "started_at": "...",
    #     "completed_at": "...",
    #     "output": {...},
    #     "error": null,
    #   },
    #   ...
    # ]

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    started_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Celery task tracking
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    playbook: Mapped["Playbook"] = relationship("Playbook", back_populates="executions")
    tenant: Mapped["Tenant"] = relationship("Tenant")
    approvals: Mapped[list["PlaybookApproval"]] = relationship(
        "PlaybookApproval", back_populates="execution", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PlaybookExecution {self.id} ({self.status.value})>"


class PlaybookApproval(Base):
    """Approval queue for playbook steps requiring human approval."""

    __tablename__ = "playbook_approvals"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("playbook_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Step reference
    step_id: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Status
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING
    )

    # Context for approver
    context: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    # Context:
    # {
    #   "playbook_name": "Block Malicious IP",
    #   "action": "block_ip",
    #   "parameters": {"ip": "1.2.3.4"},
    #   "alert_title": "Suspicious Activity",
    #   "risk_level": "high",
    # }

    # Approval details
    required_approvers: Mapped[list[str]] = mapped_column(ArrayType(String), default=list)
    approved_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    execution: Mapped["PlaybookExecution"] = relationship(
        "PlaybookExecution", back_populates="approvals"
    )
    tenant: Mapped["Tenant"] = relationship("Tenant")
    approver: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<PlaybookApproval {self.step_name} ({self.status.value})>"


class RulePlaybookBinding(Base):
    """Binding between detection rules and playbooks."""

    __tablename__ = "rule_playbook_bindings"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("detection_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    playbook_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("playbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Binding configuration
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Lower = higher priority
    conditions: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    # Additional conditions beyond rule match:
    # {
    #   "min_severity": "high",
    #   "only_during_business_hours": false,
    #   "rate_limit_per_hour": 10,
    # }

    # Timestamps
    created_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    rule: Mapped["DetectionRule"] = relationship("DetectionRule")
    playbook: Mapped["Playbook"] = relationship("Playbook", back_populates="rule_bindings")
    tenant: Mapped["Tenant"] = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<RulePlaybookBinding {self.rule_id} -> {self.playbook_id}>"
