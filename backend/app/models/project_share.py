"""ProjectShare ORM model — v0.4 project sharing."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class ProjectShare(Base):
    __tablename__ = "project_shares"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(
        String, nullable=False, default="viewer"
    )
    shared_by: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "idx_project_shares_unique",
            "project_id",
            "user_id",
            unique=True,
            sqlite_where=revoked_at.is_(None),
        ),
        Index(
            "idx_project_shares_user",
            "user_id",
            sqlite_where=revoked_at.is_(None),
        ),
    )
