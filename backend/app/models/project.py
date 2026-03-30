"""Project ORM model — aligned with data-model.md §3.1."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    user_query: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    output_types: Mapped[list] = mapped_column(
        JSON, nullable=False, default=lambda: ["full_review"]
    )
    output_language: Mapped[str] = mapped_column(
        String, nullable=False, default="zh"
    )
    citation_style: Mapped[str] = mapped_column(
        String, nullable=False, default="apa"
    )
    search_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    paper_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Relationships ──
    project_papers: Mapped[list["ProjectPaper"]] = relationship(
        back_populates="project", lazy="selectin"
    )
    review_outputs: Mapped[list["ReviewOutput"]] = relationship(
        back_populates="project", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_projects_status", "status", sqlite_where=deleted_at.is_(None)),
        Index("idx_projects_created", "created_at"),
        Index(
            "idx_projects_user",
            "user_id",
            sqlite_where=(user_id.isnot(None)) & (deleted_at.is_(None)),
        ),
    )
