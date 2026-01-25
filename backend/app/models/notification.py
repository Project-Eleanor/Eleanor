"""Notification model for Eleanor."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationType(str, Enum):
    """Types of notifications."""

    # Case notifications
    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_ASSIGNED = "case_assigned"
    CASE_CLOSED = "case_closed"

    # Evidence notifications
    EVIDENCE_UPLOADED = "evidence_uploaded"
    EVIDENCE_PROCESSED = "evidence_processed"

    # Workflow notifications
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

    # Detection/Alert notifications
    DETECTION_HIT = "detection_hit"
    ALERT_TRIGGERED = "alert_triggered"

    # System notifications
    SYSTEM_ALERT = "system_alert"
    INTEGRATION_ERROR = "integration_error"
    SCHEDULED_TASK = "scheduled_task"

    # User notifications
    MENTION = "mention"
    COMMENT = "comment"


class NotificationSeverity(str, Enum):
    """Notification severity levels."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Notification(Base):
    """User notification model."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    type: Mapped[NotificationType] = mapped_column(String(50), nullable=False)
    severity: Mapped[NotificationSeverity] = mapped_column(
        String(20),
        nullable=False,
        default=NotificationSeverity.INFO
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500))  # URL to navigate to
    icon: Mapped[str | None] = mapped_column(String(50))  # Material icon name
    data: Mapped[dict | None] = mapped_column(JSONB)  # Additional context data

    # Status
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", backref="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.id}: {self.type} for user {self.user_id}>"


class NotificationPreference(Base):
    """User notification preferences."""

    __tablename__ = "notification_preferences"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Channel preferences
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Type preferences (JSON map of notification_type -> enabled)
    type_preferences: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Quiet hours
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5))  # HH:MM format
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    user = relationship("User", backref="notification_preferences")
