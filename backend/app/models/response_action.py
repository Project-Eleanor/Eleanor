"""Response action models for tracking host isolation and response actions."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import JSONBType, UUIDType


class ResponseActionType(str, Enum):
    """Types of response actions."""

    ISOLATE = "isolate"
    RELEASE = "release"
    QUARANTINE_FILE = "quarantine_file"
    KILL_PROCESS = "kill_process"
    COLLECT_ARTIFACT = "collect_artifact"
    BLOCK_IP = "block_ip"
    DISABLE_USER = "disable_user"
    CUSTOM = "custom"


class ResponseActionStatus(str, Enum):
    """Status of a response action."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResponseAction(Base):
    """Track response actions performed on endpoints."""

    __tablename__ = "response_actions"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=False, index=True
    )
    case_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("cases.id"), nullable=True, index=True
    )

    # Action details
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ResponseActionStatus.PENDING.value, index=True
    )

    # Target information
    client_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_details: Mapped[dict] = mapped_column(
        JSONBType(), default=dict
    )  # file_path, pid, ip_address, etc.

    # Execution details
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    case = relationship("Case")
    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<ResponseAction {self.action_type} on {self.client_id}>"
