"""ReviewOutput ORM model — aligned with data-model.md §6.1."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ReviewOutput(Base):
    __tablename__ = "review_outputs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), nullable=False
    )
    output_type: Mapped[str] = mapped_column(String, nullable=False)

    # ── Content ──
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    outline: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content: Mapped[str | None] = mapped_column(String, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    references: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Versioning ──
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("review_outputs.id"), nullable=True
    )
    revision_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Config ──
    language: Mapped[str] = mapped_column(String, nullable=False, default="zh")
    citation_style: Mapped[str] = mapped_column(
        String, nullable=False, default="apa"
    )
    writing_style: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Citation verification ──
    citation_verification: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Export record ──
    export_formats: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Timestamps ──
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Relationships ──
    project: Mapped["Project"] = relationship(back_populates="review_outputs")
    parent: Mapped["ReviewOutput | None"] = relationship(
        remote_side=[id], lazy="selectin"
    )

    __table_args__ = (
        Index(
            "idx_outputs_project",
            "project_id",
            sqlite_where=deleted_at.is_(None),
        ),
        Index(
            "idx_outputs_type",
            "output_type",
            sqlite_where=deleted_at.is_(None),
        ),
        Index(
            "idx_outputs_project_type",
            "project_id",
            "output_type",
            sqlite_where=deleted_at.is_(None),
        ),
    )
