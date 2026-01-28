"""Graph models for investigation visualizations."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import JSONBType, UUIDType

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class SavedGraph(Base):
    """Saved investigation graph with layout and configuration."""

    __tablename__ = "saved_graphs"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Associated case
    case_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Graph definition (nodes, edges, positions, styling)
    definition: Mapped[dict] = mapped_column(JSONBType(), nullable=False, default=dict)

    # Graph configuration (layout settings, filters, etc.)
    config: Mapped[dict] = mapped_column(JSONBType(), nullable=False, default=dict)

    # Ownership
    created_by: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    creator: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<SavedGraph {self.name} (case={self.case_id})>"
