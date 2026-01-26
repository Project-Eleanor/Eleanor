"""Parsing job model for tracking evidence parsing operations."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import JSONBType, UUIDType

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.evidence import Evidence
    from app.models.user import User


class ParsingJobStatus(str, enum.Enum):
    """Status of a parsing job."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParsingJob(Base):
    """Tracks parsing job execution and progress."""

    __tablename__ = "parsing_jobs"

    id: Mapped[UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid4
    )

    # References
    evidence_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Celery task tracking
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Parser configuration
    parser_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "windows_registry", "prefetch", "mft"
    parser_hint: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # User-provided hint for parser selection

    # Job status
    status: Mapped[ParsingJobStatus] = mapped_column(
        Enum(ParsingJobStatus),
        nullable=False,
        default=ParsingJobStatus.PENDING,
        index=True,
    )

    # Progress tracking
    events_parsed: Mapped[int] = mapped_column(Integer, default=0)
    events_indexed: Mapped[int] = mapped_column(Integer, default=0)
    events_failed: Mapped[int] = mapped_column(Integer, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # Configuration
    config: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # Results summary
    results_summary: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # User who submitted the job
    submitted_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    evidence: Mapped["Evidence"] = relationship("Evidence")
    case: Mapped["Case"] = relationship("Case")
    submitter: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ParsingJob {self.id} ({self.parser_type}: {self.status.value})>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def mark_queued(self, celery_task_id: str) -> None:
        """Mark job as queued with Celery task ID."""
        self.status = ParsingJobStatus.QUEUED
        self.celery_task_id = celery_task_id

    def mark_running(self) -> None:
        """Mark job as running."""
        self.status = ParsingJobStatus.RUNNING
        self.started_at = datetime.utcnow()

    def mark_completed(
        self,
        events_parsed: int,
        events_indexed: int,
        results_summary: dict | None = None,
    ) -> None:
        """Mark job as completed with results."""
        self.status = ParsingJobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.events_parsed = events_parsed
        self.events_indexed = events_indexed
        self.progress_percent = 100
        if results_summary:
            self.results_summary = results_summary

    def mark_failed(self, error_message: str, error_details: dict | None = None) -> None:
        """Mark job as failed with error information."""
        self.status = ParsingJobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        if error_details:
            self.error_details = error_details

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = ParsingJobStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    def update_progress(
        self,
        events_parsed: int,
        events_indexed: int,
        progress_percent: int,
    ) -> None:
        """Update job progress."""
        self.events_parsed = events_parsed
        self.events_indexed = events_indexed
        self.progress_percent = min(progress_percent, 100)
