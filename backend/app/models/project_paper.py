"""ProjectPaper ORM model — aligned with data-model.md §7.1."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ProjectPaper(Base):
    __tablename__ = "project_papers"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), nullable=False
    )
    paper_id: Mapped[str] = mapped_column(
        String, ForeignKey("papers.id"), nullable=False
    )

    # ── Status ──
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="candidate"
    )

    # ── Source info ──
    found_by: Mapped[str | None] = mapped_column(String, nullable=True)
    search_query: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Ranking ──
    relevance_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Timestamps ──
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Relationships ──
    project: Mapped["Project"] = relationship(back_populates="project_papers")
    paper: Mapped["Paper"] = relationship(lazy="selectin")

    __table_args__ = (
        Index(
            "idx_pp_unique_active",
            "project_id",
            "paper_id",
            unique=True,
            sqlite_where=deleted_at.is_(None),
        ),
        Index(
            "idx_pp_project",
            "project_id",
            sqlite_where=deleted_at.is_(None),
        ),
        Index(
            "idx_pp_paper",
            "paper_id",
            sqlite_where=deleted_at.is_(None),
        ),
        Index(
            "idx_pp_status",
            "project_id",
            "status",
            sqlite_where=deleted_at.is_(None),
        ),
    )
