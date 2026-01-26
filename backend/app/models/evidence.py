"""Evidence model with chain of custody for Eleanor."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import INETType, JSONBType, UUIDType

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class EvidenceType(str, enum.Enum):
    """Types of evidence."""

    DISK_IMAGE = "disk_image"
    MEMORY_DUMP = "memory"
    LOGS = "logs"
    TRIAGE = "triage"
    NETWORK_CAPTURE = "pcap"
    ARTIFACT = "artifact"
    DOCUMENT = "document"
    MALWARE_SAMPLE = "malware"
    OTHER = "other"


class EvidenceStatus(str, enum.Enum):
    """Evidence processing status."""

    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class Evidence(Base):
    """Evidence file model with integrity tracking."""

    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Hashes for integrity
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sha1: Mapped[str | None] = mapped_column(String(40), nullable=True)
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True)

    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(EvidenceType), nullable=False, default=EvidenceType.OTHER
    )
    status: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus), nullable=False, default=EvidenceStatus.PENDING
    )

    # Source information
    source_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    collected_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Upload information
    uploaded_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Description and notes
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_metadata: Mapped[dict] = mapped_column(JSONBType(), default=dict)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="evidence")
    uploader: Mapped["User | None"] = relationship("User")
    custody_events: Mapped[list["CustodyEvent"]] = relationship(
        "CustodyEvent", back_populates="evidence", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Evidence {self.filename} ({self.evidence_type.value})>"


class CustodyAction(str, enum.Enum):
    """Chain of custody action types."""

    UPLOADED = "uploaded"
    ACCESSED = "accessed"
    DOWNLOADED = "downloaded"
    EXPORTED = "exported"
    TRANSFERRED = "transferred"
    VERIFIED = "verified"
    MODIFIED = "modified"
    DELETED = "deleted"


class CustodyEvent(Base):
    """Chain of custody event tracking."""

    __tablename__ = "custody_events"

    id: Mapped[UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid4
    )
    evidence_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[CustodyAction] = mapped_column(
        Enum(CustodyAction), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INETType(), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    evidence: Mapped["Evidence"] = relationship(
        "Evidence", back_populates="custody_events"
    )
    actor: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<CustodyEvent {self.action.value} on {self.evidence_id}>"
