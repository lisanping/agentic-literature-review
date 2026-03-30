"""PaperAnalysis ORM model — aligned with data-model.md §5.1."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class PaperAnalysis(Base):
    __tablename__ = "paper_analyses"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), nullable=False
    )
    paper_id: Mapped[str] = mapped_column(
        String, ForeignKey("papers.id"), nullable=False
    )

    # ── Structured summary ──
    objective: Mapped[str | None] = mapped_column(String, nullable=True)
    methodology: Mapped[str | None] = mapped_column(String, nullable=True)
    datasets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    findings: Mapped[str | None] = mapped_column(String, nullable=True)
    limitations: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Methodology details (for Methodology Review output) ──
    method_category: Mapped[str | None] = mapped_column(String, nullable=True)
    method_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Key concepts ──
    key_concepts: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Paper relations ──
    relations: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Quality assessment (filled by Critic Agent) ──
    quality_score: Mapped[float | None] = mapped_column(nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Relevance ──
    relevance_score: Mapped[float | None] = mapped_column(nullable=True)

    # ── Analysis depth ──
    analysis_depth: Mapped[str] = mapped_column(
        String, nullable=False, default="abstract_only"
    )

    # ── Meta ──
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Soft delete ──
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Relationships ──
    project: Mapped["Project"] = relationship(lazy="selectin")
    paper: Mapped["Paper"] = relationship(lazy="selectin")

    __table_args__ = (
        Index(
            "idx_analysis_unique_active",
            "project_id",
            "paper_id",
            unique=True,
            sqlite_where=deleted_at.is_(None),
        ),
        Index(
            "idx_analysis_project",
            "project_id",
            sqlite_where=deleted_at.is_(None),
        ),
        Index(
            "idx_analysis_paper",
            "paper_id",
            sqlite_where=deleted_at.is_(None),
        ),
    )
