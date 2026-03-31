"""AuditLog ORM model — v0.4 audit trail."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_audit_log_user", "user_id", "created_at"),
        Index("idx_audit_log_action", "action", "created_at"),
    )
