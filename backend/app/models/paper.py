"""Paper and PaperFulltext ORM models — aligned with data-model.md §4.1."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── External identifiers (used for deduplication) ──
    doi: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    s2_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    arxiv_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    openalex_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    pmid: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    # ── Basic metadata ──
    title: Mapped[str] = mapped_column(String, nullable=False)
    authors: Mapped[list] = mapped_column(JSON, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String, nullable=True)
    abstract: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Citation statistics ──
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    reference_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Source ──
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    open_access: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── File storage ──
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Timestamps ──
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ──
    fulltext: Mapped["PaperFulltext | None"] = relationship(
        back_populates="paper", uselist=False, lazy="selectin"
    )

    __table_args__ = (
        Index("idx_papers_doi", "doi", sqlite_where=doi.isnot(None)),
        Index("idx_papers_s2_id", "s2_id", sqlite_where=s2_id.isnot(None)),
        Index("idx_papers_arxiv", "arxiv_id", sqlite_where=arxiv_id.isnot(None)),
        Index("idx_papers_openalex", "openalex_id", sqlite_where=openalex_id.isnot(None)),
        Index("idx_papers_pmid", "pmid", sqlite_where=pmid.isnot(None)),
        Index("idx_papers_year", "year"),
        Index("idx_papers_title", "title"),
    )


class PaperFulltext(Base):
    """Stores parsed full-text separately from the papers table to avoid bloat."""

    __tablename__ = "paper_fulltext"

    paper_id: Mapped[str] = mapped_column(
        String, ForeignKey("papers.id"), primary_key=True
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    parser_used: Mapped[str | None] = mapped_column(String, nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # ── Relationship ──
    paper: Mapped["Paper"] = relationship(back_populates="fulltext")
