"""Workbook and saved query models for Eleanor."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SavedQuery(Base):
    """Saved search query for hunting."""

    __tablename__ = "saved_queries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    indices: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    mitre_techniques: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    creator = relationship("User")

    def __repr__(self) -> str:
        return f"<SavedQuery {self.name}>"


class Workbook(Base):
    """Dashboard workbook with visualization tiles."""

    __tablename__ = "workbooks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    creator = relationship("User")

    def __repr__(self) -> str:
        return f"<Workbook {self.name}>"
