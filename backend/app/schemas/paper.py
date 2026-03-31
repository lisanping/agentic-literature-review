"""Pydantic schemas for Paper — request/response models."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import PaperRelationType, PaperSourceType


class PaperMetadata(BaseModel):
    """Unified paper metadata — output format for all data source adapters."""

    title: str
    authors: list[str]
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    s2_id: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    citation_count: int = 0
    reference_count: int = 0
    source: PaperSourceType
    source_url: str | None = None
    pdf_url: str | None = None
    url: str | None = None
    open_access: bool = False


class PaperRelation(BaseModel):
    """Relation between two papers."""

    target_paper_id: str
    relation_type: PaperRelationType
    evidence: str | None = None


class PaperAnalysisResponse(BaseModel):
    """Paper analysis result response."""

    model_config = {"from_attributes": True}

    paper_id: str
    objective: str | None
    methodology: str | None
    datasets: list[str] | None
    findings: str | None
    limitations: str | None
    method_category: str | None
    method_details: dict | None
    key_concepts: list[str] | None
    relations: list[dict] | None
    quality_score: float | None
    relevance_score: float | None
    analysis_depth: str


class PaperResponse(BaseModel):
    """Paper detail response."""

    model_config = {"from_attributes": True}

    id: str
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    abstract: str | None
    doi: str | None
    s2_id: str | None
    arxiv_id: str | None
    openalex_id: str | None = None
    pmid: str | None = None
    citation_count: int
    source: PaperSourceType
    pdf_url: str | None
    pdf_available: bool = False
    open_access: bool
    analysis: PaperAnalysisResponse | None = None


class ProjectPaperResponse(BaseModel):
    """Paper within a project context."""

    model_config = {"from_attributes": True}

    paper: PaperResponse
    status: str
    found_by: str | None
    relevance_rank: int | None
    added_at: datetime
