"""Base processor interface and data structures.

Defines the abstract interface for case processors that run
automatically in response to case events.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ProcessorTrigger(str, Enum):
    """Events that can trigger a processor."""

    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_STATUS_CHANGED = "case_status_changed"
    CASE_CLOSED = "case_closed"
    EVIDENCE_UPLOADED = "evidence_uploaded"
    EVIDENCE_PROCESSED = "evidence_processed"
    IOC_ADDED = "ioc_added"
    MANUAL = "manual"


class ProcessorStatus(str, Enum):
    """Status of a processor execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProcessorContext:
    """Context passed to processors during execution."""

    trigger: ProcessorTrigger
    case_id: UUID | None = None
    evidence_id: UUID | None = None
    user_id: UUID | None = None
    event_data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Services available to processors
    db_session: Any = None
    redis_client: Any = None
    elasticsearch_client: Any = None
    adapter_registry: Any = None


@dataclass
class ProcessorResult:
    """Result of a processor execution."""

    processor_name: str
    status: ProcessorStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "processor_name": self.processor_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "data": self.data,
            "errors": self.errors,
            "changes": self.changes,
        }


class BaseProcessor(ABC):
    """Abstract base class for case processors.

    Processors are automated actions that run in response to case events.
    They can enrich data, sync with external systems, calculate metrics, etc.

    Subclasses must implement:
    - name: Unique processor identifier
    - triggers: List of events that trigger this processor
    - process(): The main processing logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this processor."""
        ...

    @property
    @abstractmethod
    def triggers(self) -> list[ProcessorTrigger]:
        """Events that trigger this processor."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        return ""

    @property
    def enabled(self) -> bool:
        """Whether this processor is enabled."""
        return True

    @property
    def priority(self) -> int:
        """Priority for execution order (lower = higher priority)."""
        return 100

    @property
    def timeout_seconds(self) -> int:
        """Maximum execution time in seconds."""
        return 60

    def should_run(self, context: ProcessorContext) -> bool:
        """Determine if processor should run for given context.

        Override to add custom conditions beyond trigger matching.

        Args:
            context: Execution context

        Returns:
            True if processor should run
        """
        return context.trigger in self.triggers

    @abstractmethod
    async def process(self, context: ProcessorContext) -> ProcessorResult:
        """Execute the processor logic.

        Args:
            context: Execution context with case/evidence info

        Returns:
            ProcessorResult with status and any output data
        """
        ...

    async def on_error(self, context: ProcessorContext, error: Exception) -> None:
        """Handle errors during processing.

        Override to add custom error handling (notifications, logging, etc.)

        Args:
            context: Execution context
            error: The exception that occurred
        """
        pass

    def _create_result(
        self,
        status: ProcessorStatus,
        started_at: datetime,
        message: str | None = None,
        data: dict | None = None,
        errors: list | None = None,
        changes: list | None = None,
    ) -> ProcessorResult:
        """Helper to create a ProcessorResult.

        Args:
            status: Execution status
            started_at: When execution started
            message: Optional status message
            data: Optional output data
            errors: Optional list of errors
            changes: Optional list of changes made

        Returns:
            Populated ProcessorResult
        """
        now = datetime.now(UTC)
        duration = int((now - started_at).total_seconds() * 1000)

        return ProcessorResult(
            processor_name=self.name,
            status=status,
            started_at=started_at,
            completed_at=now,
            duration_ms=duration,
            message=message,
            data=data or {},
            errors=errors or [],
            changes=changes or [],
        )
