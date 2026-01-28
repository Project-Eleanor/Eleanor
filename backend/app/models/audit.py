"""Audit log model for Eleanor."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.compat import INETType, JSONBType, UUIDType


class AuditLog(Base):
    """Audit log for tracking all system actions."""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id"), nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    resource_id: Mapped[UUID | None] = mapped_column(UUIDType(), nullable=True)
    details: Mapped[dict] = mapped_column(JSONBType(), default=dict)
    ip_address: Mapped[str | None] = mapped_column(INETType(), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.username}>"
